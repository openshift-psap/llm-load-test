from abc import ABC, abstractmethod

from result import RequestResult


class Plugin(ABC):
    def __init__(self, args):
        self.args = args

    @abstractmethod
    def request_func(self, query: dict, user_id: int, test_end_time: float) -> RequestResult:
        pass
