"""Main result class."""

from typing import Optional


class RequestResult:
    """Request result class."""

    def __init__(self, user_id, input_id, input_tokens=None):
        """Init method."""
        self.user_id: int = user_id
        self.input_id: int = input_id
        self.input_tokens: Optional[int] = input_tokens
        self.output_text: Optional[str] = None
        self.output_tokens: Optional[int] = None
        self.output_tokens_before_timeout: Optional[int] = None
        self.start_time: Optional[float] = None
        self.ack_time: Optional[float] = None
        self.first_token_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.response_time: Optional[float] = None
        self.tt_ack: Optional[float] = None
        self.ttft: Optional[float] = None
        self.itl: Optional[float] = None
        self.tpot: Optional[float] = None
        self.stop_reason: Optional[str] = None
        self.error_code: Optional[int] = None
        self.error_text: Optional[str] = None

    def asdict(self):
        """Return a dictionary."""
        # Maybe later we will want to only include some fields in the results,
        # but for now, this just puts all object fields in a dict.
        return vars(self)

    # Fill in calculated fields like response_time, tt_ack, ttft, tpot.
    def calculate_results(self):
        """Calculate the results."""
        # Only calculate results if response is error-free.
        if self.error_code is None and self.error_text is None:
            if self.end_time is not None and self.start_time is not None:
                # response_time in ms
                self.response_time = 1000 * (self.end_time - self.start_time)

            if self.ack_time is not None and self.start_time is not None:
                self.tt_ack = 1000 * (self.ack_time - self.start_time)

            if self.first_token_time is not None:
                if self.start_time is not None:
                    self.ttft = 1000 * (
                        self.first_token_time - self.start_time
                    )  # Time to first token in ms
                if self.end_time is not None and self.output_tokens is not None:
                    self.itl = (1000 * (self.end_time - self.first_token_time)) / (
                        self.output_tokens - 1
                    )  # Inter-token latency in ms. Distinct from TPOT as it excludes the first token time.

            if self.response_time is not None and self.output_tokens is not None:
                self.tpot = (
                    self.response_time / self.output_tokens
                )  # Time per output token in ms
