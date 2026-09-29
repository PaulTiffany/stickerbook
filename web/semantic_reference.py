"""One admitted discourse referent, separate from input and world history."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingSemanticReference:
    subject: str
    demonstration: str
    path_ref: str
    source_episode: str
    principal: str
    page: str

    def describe(self) -> dict:
        return {
            "subject": self.subject,
            "demonstration": self.demonstration,
            "kind": "page-path",
            "pathRef": self.path_ref,
            "sourceEpisode": self.source_episode,
            "principal": self.principal,
            "page": self.page,
        }
