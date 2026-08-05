"""
Security utilities for the middleware API.
"""
import os
import time
from typing import Set, Dict
from collections import defaultdict, deque
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/security.log", "SecurityLogger")


class IPBlocker:
    """
    Simple IP blocking mechanism based on failed authentication attempts.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        block_duration: int = 3600,  # 1 hour in seconds
        time_window: int = 300,  # 5 minutes in seconds
    ):
        self.max_attempts = max_attempts
        self.block_duration = block_duration
        self.time_window = time_window

        # Track blocked IPs: {ip: block_expiry_time}
        self.blocked_ips: Dict[str, float] = {}

        # Track failed attempts: {ip: [timestamp1, timestamp2, ...]}
        self.failed_attempts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_attempts))

        logger.info(
            f"IPBlocker initialized: max_attempts={max_attempts}, "
            f"block_duration={block_duration}s, time_window={time_window}s"
        )

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            else:
                # Block expired, remove it
                del self.blocked_ips[ip]
                logger.info(f"IP {ip} block expired")
                return False
        return False

    def record_failed_attempt(self, ip: str) -> bool:
        """Record a failed authentication attempt. Returns True if the IP was just blocked."""
        current_time = time.time()

        # Clean old attempts outside the time window
        attempts = self.failed_attempts[ip]
        while attempts and current_time - attempts[0] > self.time_window:
            attempts.popleft()

        # Add new attempt
        attempts.append(current_time)
        logger.warning(f"Failed auth attempt from {ip} ({len(attempts)}/{self.max_attempts})")

        # Check if should be blocked
        if len(attempts) >= self.max_attempts:
            self.block_ip(ip)
            return True

        return False

    def block_ip(self, ip: str) -> None:
        """Block an IP address for the configured duration."""
        block_expiry = time.time() + self.block_duration
        self.blocked_ips[ip] = block_expiry
        logger.error(f"Blocked IP: {ip} until {time.ctime(block_expiry)}")

    def unblock_ip(self, ip: str) -> None:
        """Manually unblock an IP address."""
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            logger.info(f"IP {ip} manually unblocked")

    def get_blocked_ips(self) -> Set[str]:
        """Get all currently blocked IPs."""
        current_time = time.time()
        # Clean expired blocks
        expired = [ip for ip, expiry in self.blocked_ips.items() if current_time >= expiry]
        for ip in expired:
            del self.blocked_ips[ip]

        return set(self.blocked_ips.keys())

    def reset_attempts(self, ip: str) -> None:
        """Reset failed attempts for an IP (e.g., after successful auth)."""
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]


class IPWhitelist:
    """
    IP whitelist management.
    """

    def __init__(self):
        """Initialize IP whitelist from environment variable."""
        whitelist_str = os.getenv("IP_WHITELIST", "")
        self.whitelist: Set[str] = set(
            ip.strip() for ip in whitelist_str.split(",") if ip.strip()
        )

        if self.whitelist:
            logger.info(f"IP Whitelist enabled: {len(self.whitelist)} IPs")
        else:
            logger.info("IP Whitelist disabled (empty)")

    def is_whitelisted(self, ip: str) -> bool:
        """Check if an IP is whitelisted."""
        return ip in self.whitelist if self.whitelist else True  # Allow all if empty

    def add_ip(self, ip: str) -> None:
        """Add an IP to the whitelist."""
        self.whitelist.add(ip)
        logger.info(f"Added {ip} to whitelist")

    def remove_ip(self, ip: str) -> None:
        """Remove an IP from the whitelist."""
        self.whitelist.discard(ip)
        logger.info(f"Removed {ip} from whitelist")


class SecurityMonitor:
    """
    Monitor and log security events.
    """

    def __init__(self):
        self.suspicious_patterns = {
            "sql_injection": ["'", "\"", "OR", "SELECT", "UNION", "DROP", "--", ";"],
            "xss": ["<script>", "javascript:", "onerror=", "onload="],
            "path_traversal": ["../", "..\\", "/etc/", "c:\\"],
        }

    def check_suspicious_input(self, data: str) -> Dict[str, bool]:
        """Check input for SQL injection, XSS, and path traversal patterns."""
        detected = {}
        data_lower = data.lower()

        for pattern_type, patterns in self.suspicious_patterns.items():
            detected[pattern_type] = any(
                pattern.lower() in data_lower for pattern in patterns
            )

        return detected

    def log_security_event(
        self, event_type: str, ip: str, details: str, severity: str = "WARNING"
    ):
        """Log a security event."""
        log_msg = f"[{event_type}] IP={ip} | {details}"

        if severity == "CRITICAL":
            logger.critical(log_msg)
        elif severity == "ERROR":
            logger.error(log_msg)
        else:
            logger.warning(log_msg)


# Singleton instances
ip_blocker = IPBlocker()
ip_whitelist = IPWhitelist()
security_monitor = SecurityMonitor()
