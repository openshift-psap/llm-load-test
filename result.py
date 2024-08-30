"""Main result class."""


class RequestResult:
    """Request result class."""

    def __init__(self, user_id, input_id, input_tokens=None):
        """Init method."""
        self.user_id = user_id
        self.input_id = input_id
        self.input_tokens = input_tokens
        self.output_text = None
        self.output_tokens = None
        self.output_tokens_before_timeout = None
        self.start_time = None
        self.ack_time = None
        self.first_token_time = None
        self.end_time = None
        self.response_time = None
        self.tt_ack = None
        self.ttft = None
        self.itl = None
        self.tpot = None
        self.stop_reason = None
        self.error_code = None
        self.error_text = None

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
            # response_time in seconds
            self.response_time = 1000 * (self.end_time - self.start_time)

            if self.ack_time is not None:
                self.tt_ack = 1000 * (self.ack_time - self.start_time)

            if self.first_token_time is not None:
                self.ttft = 1000 * (
                    self.first_token_time - self.start_time
                )  # Time to first token in ms
                self.itl = (1000 * (self.end_time - self.first_token_time)) / (
                    self.output_tokens - 1
                )  # Inter-token latency in ms. Distinct from TPOT as it excludes the first token time.

            self.tpot = (
                self.response_time / self.output_tokens
            )  # Time per output token in ms
