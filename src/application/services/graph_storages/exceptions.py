from src.domain.exceptions import GraphStorageError


class DomainNotFoundError(GraphStorageError):
    def __init__(self, domain_id: str) -> None:
        super().__init__(f"Domain {domain_id!r} not found")
        self.domain_id = domain_id


class ConceptNotFoundError(GraphStorageError):
    def __init__(self, concept_id: str) -> None:
        super().__init__(f"Concept {concept_id!r} not found")
        self.concept_id = concept_id


class CardNotFoundError(GraphStorageError):
    def __init__(self, card_id: str) -> None:
        super().__init__(f"Card {card_id!r} not found")
        self.card_id = card_id
