groq.RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `mixtral-8x7b-32768` in organization `org_01hybdqdm9f2fbwer4akc0y8ep` on tokens per minute (TPM): Limit 5000, Used 0, Requested ~26992. Please try again in 4m23.904s. Visit https://console.groq.com/docs/rate-limits for more information.', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}


    raise self._make_status_error_from_response(err.response) from None
groq.BadRequestError: Error code: 400 - {'error': {'message': 'Please reduce the length of the messages or completion.', 'type': 'invalid_request_error', 'param': 'messages', 'code': 'context_length_exceeded'}}


    raise self._make_status_error_from_response(err.response) from None
groq.RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `mixtral-8x7b-32768` in organization `org_01hybdqdm9f2fbwer4akc0y8ep` on tokens per minute (TPM): Limit 5000, Used 0, Requested ~26992. Please try again in 4m23.904s. Visit https://console.groq.com/docs/rate-limits for more information.', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}