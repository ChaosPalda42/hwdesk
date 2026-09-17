from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from time import time
from datetime import datetime, timezone


class HandoverTokens:
    def __init__(self, secret: str, max_age_hours: int):
        self.secret = secret
        self.max_age_hours = max_age_hours

    def issue(self, handover_id: int, email: str) -> str:
        """Issue a handover token with the given handover_id and email."""
        serializer = URLSafeTimedSerializer(self.secret, salt="handover")
        return serializer.dumps({"handover_id": handover_id, "email": email.lower()})

    def verify(self, token: str, now_offset_seconds: int = 0) -> dict | None:
        """Verify a handover token and return its contents or None if invalid."""
        serializer = URLSafeTimedSerializer(self.secret, salt="handover")
        try:
            # Check if token is valid and not expired
            result = serializer.loads(token, max_age=self.max_age_hours * 3600, return_timestamp=True)
            # If we get here, the token is valid and not expired according to max_age
            # The result is a tuple: (data, timestamp)
            data, timestamp = result
            
            # Convert timestamp to seconds since epoch for comparison
            if hasattr(timestamp, 'timestamp'):
                # It's a datetime object, convert to timestamp
                token_timestamp = timestamp.timestamp()
            else:
                # It's already a timestamp
                token_timestamp = timestamp
            
            # Calculate what time should be considered "now" with the offset
            current_time_with_offset = time() + now_offset_seconds
            
            # Check if the token is expired based on max_age_hours and offset
            if current_time_with_offset - token_timestamp > self.max_age_hours * 3600:
                return None
                
            return data
        except (BadSignature, SignatureExpired):
            # Token is either malformed or expired
            return None