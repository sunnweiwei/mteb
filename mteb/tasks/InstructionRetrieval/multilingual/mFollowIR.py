from __future__ import annotations

from collections import defaultdict

import datasets

from mteb.abstasks.MultilingualTask import MultilingualTask
from mteb.abstasks.TaskMetadata import TaskMetadata

from ....abstasks.AbsTaskInstructionRetrieval import AbsTaskInstructionRetrieval

_LANGUAGES = {
    "fas": ["fas-Arab"],
    "rus": ["rus-Cyrl"],
    "zho": ["zho-Hans"],
}

_LANGUAGES_CLIR = {
    "eng.fas": ["eng-Latn", "fas-Arab"],
    "eng.rus": ["eng-Latn", "rus-Cyrl"],
    "eng.zho": ["eng-Latn", "zho-Hans"],
}


def _build_lang_pair(langs: list[str]) -> str:
    """Builds a language pair separated by a dash.
    e.g., ['eng-Latn', 'deu-Latn'] -> 'eng-deu'.
    """
    return langs[0].split("-")[0] + "-" + langs[1].split("-")[0]


def extend_lang_pairs() -> dict[str, list[str]]:
    eval_langs = {}
    for langs in _LANGUAGES_CLIR.values():
        lang_pair = _build_lang_pair(langs)
        eval_langs[lang_pair] = langs
    return eval_langs


_CLIR_LANGS = extend_lang_pairs()

EVAL_SPLIT = "test"


def load_data(
    path: str,
    langs: list,
    eval_splits: list,
    cache_dir: str | None = None,
    revision: str | None = None,
):
    corpus = {lang: {EVAL_SPLIT: {}} for lang in langs}
    queries = {lang: {EVAL_SPLIT: {}} for lang in langs}
    og_relevant_docs = {lang: {EVAL_SPLIT: {}} for lang in langs}
    changed_relevant_docs = {lang: {EVAL_SPLIT: {}} for lang in langs}
    top_ranked = {lang: {EVAL_SPLIT: {}} for lang in langs}

    for lang in langs:
        if "-" in lang:
            loading_lang = lang.split("-")[1]  # don't care about the eng part
        else:
            loading_lang = lang

        # Load corpus data
        corpus_data = datasets.load_dataset(
            path,
            f"corpus-{loading_lang}",
            cache_dir=cache_dir,
            revision=revision,
            trust_remote_code=True,
        )
        corpus[lang][EVAL_SPLIT] = {
            row["_id"]: {"title": row["title"], "text": row["text"]}
            for row in corpus_data["corpus"]
        }

        # Load queries data
        queries_data = datasets.load_dataset(
            path,
            f"queries-{loading_lang}",
            cache_dir=cache_dir,
            revision=revision,
            trust_remote_code=True,
        )
        queries[lang][EVAL_SPLIT] = {
            row["_id"]: {
                "text": row["text"],
                "instruction_og": row["instruction_og"],
                "instruction_changed": row["instruction_changed"],
                "keywords": row["keywords"] if "keywords" in row else None,
                "short_query": row["short_query"] if "short_query" in row else None,
            }
            for row in queries_data["queries"]
        }

        # Load qrels_og data
        qrels_og_data = datasets.load_dataset(
            path,
            f"qrels_og-{loading_lang}",
            cache_dir=cache_dir,
            revision=revision,
            trust_remote_code=True,
        )
        for row in qrels_og_data[EVAL_SPLIT]:
            if row["query-id"] not in og_relevant_docs[lang][EVAL_SPLIT]:
                og_relevant_docs[lang][EVAL_SPLIT][row["query-id"]] = {
                    row["corpus-id"]: int(row["score"])
                }
            else:
                og_relevant_docs[lang][EVAL_SPLIT][row["query-id"]][
                    row["corpus-id"]
                ] = int(row["score"])

        # Load qrels_changed data
        qrels_changed_data = datasets.load_dataset(
            path,
            f"qrels_changed-{loading_lang}",
            cache_dir=cache_dir,
            revision=revision,
            trust_remote_code=True,
        )
        for row in qrels_changed_data[EVAL_SPLIT]:
            if row["query-id"] not in changed_relevant_docs[lang][EVAL_SPLIT]:
                changed_relevant_docs[lang][EVAL_SPLIT][row["query-id"]] = {
                    row["corpus-id"]: int(row["score"])
                }
            else:
                changed_relevant_docs[lang][EVAL_SPLIT][row["query-id"]][
                    row["corpus-id"]
                ] = int(row["score"])

        # Load top_ranked data
        top_ranked_data = datasets.load_dataset(
            path,
            f"top_ranked-{loading_lang}",
            cache_dir=cache_dir,
            revision=revision,
            trust_remote_code=True,
        )
        for row in top_ranked_data["top_ranked"]:
            if row["qid"] not in top_ranked[lang][EVAL_SPLIT]:
                top_ranked[lang][EVAL_SPLIT][row["qid"]] = [row["pid"]]
            else:
                top_ranked[lang][EVAL_SPLIT][row["qid"]].append(row["pid"])

    # make og_instructions and changed_instructions from queries and then turn queries into just queries
    og_instructions = {lang: {EVAL_SPLIT: defaultdict(dict)} for lang in queries}
    changed_instructions = {lang: {EVAL_SPLIT: defaultdict(dict)} for lang in queries}
    queries_only = {lang: {EVAL_SPLIT: {}} for lang in queries}
    for lang in queries:
        for split in queries[lang]:
            for qid in queries[lang][split]:
                text = queries[lang][split][qid]["text"]
                og_instructions[lang][split][text] = queries[lang][split][qid][
                    "instruction_og"
                ]
                changed_instructions[lang][split][text] = queries[lang][split][qid][
                    "instruction_changed"
                ]
                queries_only[lang][split][qid] = text

    queries = queries_only

    return (
        corpus,
        queries,
        og_instructions,
        changed_instructions,
        og_relevant_docs,
        changed_relevant_docs,
        top_ranked,
    )


class mFollowIRCrossLingual(MultilingualTask, AbsTaskInstructionRetrieval):
    metadata = TaskMetadata(
        name="mFollowIRCrossLingualInstructionRetrieval",
        description="This tasks measures retrieval instruction following ability on NeuCLIR narratives for the mFollowIR benchmark on the Farsi, Russian, and Chinese languages with English queries/instructions.",
        reference="https://neuclir.github.io/",
        dataset={
            "path": "jhu-clsp/mFollowIR-cross-lingual-parquet",
            "revision": "7a82814a53229d3c8f18b2e18762a1a959dc5ff6",
        },
        type="Retrieval",
        category="s2p",
        modalities=["text"],
        eval_splits=[EVAL_SPLIT],
        eval_langs=_CLIR_LANGS,
        main_score="p-MRR",
        date=("2021-08-01", "2022-06-30"),
        domains=["News", "Written"],
        task_subtypes=[],
        license="odc-by",
        annotations_creators="expert-annotated",
        dialect=[],
        sample_creation="found",
        bibtex_citation="""@article{weller2024mfollowir,
  title={{mFollowIR: a Multilingual Benchmark for Instruction Following in Retrieval}},
  author={Weller, Orion and Chang, Benjamin and Yang, Eugene and Yarmohammadi, Mahsa and Barham, Sam and MacAvaney, Sean and Cohan, Arman and Soldaini, Luca and Van Durme, Benjamin and Lawrie, Dawn},
  journal={arXiv preprint TODO},
  year={2024}
}""",
        descriptive_stats={
            "n_samples": {"eng-fas": 40 * 2, "eng-rus": 40 * 2, "eng-zho": 43 * 2},
            "test": {
                "num_docs": 121635,
                "num_queries": 123,
                "average_document_length": 2331.0777818884367,
                "average_query_length": 81.8780487804878,
                "average_instruction_length": 389.9512195121951,
                "average_changed_instruction_length": 450.5528455284553,
                "average_relevant_docs_per_query": 10.30952380952381,
                "average_top_ranked_per_query": 1024.3902439024391,
                "hf_subset_descriptive_stats": {
                    "eng-fas": {
                        "num_docs": 41189,
                        "num_queries": 40,
                        "average_document_length": 3145.4990895627475,
                        "average_query_length": 80.075,
                        "average_instruction_length": 396.875,
                        "average_changed_instruction_length": 463.175,
                        "average_relevant_docs_per_query": 10.465116279069768,
                        "average_top_ranked_per_query": 1075,
                    },
                    "eng-rus": {
                        "num_docs": 39326,
                        "num_queries": 40,
                        "average_document_length": 2784.0813456746173,
                        "average_query_length": 81.875,
                        "average_instruction_length": 371.125,
                        "average_changed_instruction_length": 431.8,
                        "average_relevant_docs_per_query": 9.775,
                        "average_top_ranked_per_query": 1000,
                    },
                    "eng-zho": {
                        "num_docs": 41120,
                        "num_queries": 43,
                        "average_document_length": 1082.0501215953307,
                        "average_query_length": 83.55813953488372,
                        "average_instruction_length": 401.0232558139535,
                        "average_changed_instruction_length": 456.25581395348837,
                        "average_relevant_docs_per_query": 10.651162790697674,
                        "average_top_ranked_per_query": 1000,
                    },
                },
            },
        },
    )

    def load_data(self, **kwargs):
        if self.data_loaded:
            return

        (
            self.corpus,
            self.queries,
            self.og_instructions,
            self.changed_instructions,
            self.og_relevant_docs,
            self.changed_relevant_docs,
            self.top_ranked,
        ) = load_data(
            path=self.metadata_dict["dataset"]["path"],
            langs=self.metadata.eval_langs,
            eval_splits=self.metadata_dict["eval_splits"],
            cache_dir=kwargs.get("cache_dir", None),
            revision=self.metadata_dict["dataset"]["revision"],
        )

        self.data_loaded = True


class mFollowIR(MultilingualTask, AbsTaskInstructionRetrieval):
    metadata = TaskMetadata(
        name="mFollowIRInstructionRetrieval",
        description="This tasks measures retrieval instruction following ability on NeuCLIR narratives for the mFollowIR benchmark on the Farsi, Russian, and Chinese languages.",
        reference="https://neuclir.github.io/",
        dataset={
            "path": "jhu-clsp/mFollowIR-parquet",
            "revision": "2c5cdcb438eff9de6412803768ac7304d4771cdc",
        },
        type="Retrieval",
        category="s2p",
        modalities=["text"],
        eval_splits=[EVAL_SPLIT],
        eval_langs=_LANGUAGES,
        main_score="p-MRR",
        date=("2021-08-01", "2022-06-30"),
        domains=["News", "Written"],
        task_subtypes=[],
        license="odc-by",
        annotations_creators="expert-annotated",
        dialect=[],
        sample_creation="found",
        bibtex_citation="""@article{weller2024mfollowir,
  title={{mFollowIR: a Multilingual Benchmark for Instruction Following in Retrieval}},
  author={Weller, Orion and Chang, Benjamin and Yang, Eugene and Yarmohammadi, Mahsa and Barham, Sam and MacAvaney, Sean and Cohan, Arman and Soldaini, Luca and Van Durme, Benjamin and Lawrie, Dawn},
  journal={arXiv preprint TODO},
  year={2024}
}""",
        descriptive_stats={
            "n_samples": {"fas": 40 * 2, "rus": 40 * 2, "zho": 43 * 2},
            "test": {
                "num_docs": 121635,
                "num_queries": 123,
                "average_document_length": 2331.0777818884367,
                "average_query_length": 57.113821138211385,
                "average_instruction_length": 281.0650406504065,
                "average_changed_instruction_length": 326.9430894308943,
                "average_relevant_docs_per_query": 10.30952380952381,
                "average_top_ranked_per_query": 1024.3902439024391,
                "hf_subset_descriptive_stats": {
                    "fas": {
                        "num_docs": 41189,
                        "num_queries": 40,
                        "average_document_length": 3145.4990895627475,
                        "average_query_length": 72.65,
                        "average_instruction_length": 358.925,
                        "average_changed_instruction_length": 415.325,
                        "average_relevant_docs_per_query": 10.465116279069768,
                        "average_top_ranked_per_query": 1075,
                    },
                    "rus": {
                        "num_docs": 39326,
                        "num_queries": 40,
                        "average_document_length": 2784.0813456746173,
                        "average_query_length": 77.5,
                        "average_instruction_length": 387,
                        "average_changed_instruction_length": 458,
                        "average_relevant_docs_per_query": 9.775,
                        "average_top_ranked_per_query": 1000,
                    },
                    "zho": {
                        "num_docs": 41120,
                        "num_queries": 43,
                        "average_document_length": 1082.0501215953307,
                        "average_query_length": 23.697674418604652,
                        "average_instruction_length": 110.09302325581395,
                        "average_changed_instruction_length": 122.81395348837209,
                        "average_relevant_docs_per_query": 10.651162790697674,
                        "average_top_ranked_per_query": 1000,
                    },
                },
            },
        },
    )

    def load_data(self, **kwargs):
        if self.data_loaded:
            return

        (
            self.corpus,
            self.queries,
            self.og_instructions,
            self.changed_instructions,
            self.og_relevant_docs,
            self.changed_relevant_docs,
            self.top_ranked,
        ) = load_data(
            path=self.metadata_dict["dataset"]["path"],
            langs=self.metadata.eval_langs,
            eval_splits=self.metadata_dict["eval_splits"],
            cache_dir=kwargs.get("cache_dir", None),
            revision=self.metadata_dict["dataset"]["revision"],
        )

        self.data_loaded = True