# gbt-capability: socket

"""GBT小土豆V8 · OSINT 扫描核心模块

统一由 gbt_allinone.run_task 驱动（GBT 钢印体系）。

Scanner capabilities:
  dns_recon    - resolve DNS records for target
  whois_lookup - WHOIS registration data
  subdomain_enum - brute-force common subdomains
  port_scan    - TCP port enumeration
  tech_identify - web technology fingerprinting
  email_verify - email format + MX validation
  ip_geo       - IP geolocation via ipinfo.io
  social_search - social platform presence check
"""
import os
import re
import json
import time
import logging
import socket
import urllib.request
import urllib.error
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('autoclaw')


class OSINTResult:
    """Result container for OSINT findings."""

    def __init__(self, target: str, source: str, data: Any, confidence: float):
        self.target = target
        self.source = source
        self.data = data
        self.confidence = confidence
        self.timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'target': self.target,
            'source': self.source,
            'confidence': self.confidence,
            'data': self.data,
            'timestamp': self.timestamp,
        }

    def __repr__(self):
        return f"OSINTResult({self.target}, {self.source}, conf={self.confidence})"


def get_available_capabilities() -> List[Dict[str, str]]:
    """Return list of all available capabilities."""
    return [
        {'name': 'dns_recon', 'description': 'DNS record resolution'},
        {'name': 'whois_lookup', 'description': 'WHOIS domain registration lookup'},
        {'name': 'subdomain_enum', 'description': 'Subdomain enumeration via DNS brute force'},
        {'name': 'port_scan', 'description': 'Common TCP port scan'},
        {'name': 'tech_identify', 'description': 'Web technology fingerprinting'},
        {'name': 'email_verify', 'description': 'Email address format validation and domain check'},
        {'name': 'ip_geo', 'description': 'IP geolocation via ipinfo.io API'},
        {'name': 'social_search', 'description': 'Social media username presence check'},
    ]


# ============================================================
# Capability 1: DNS Recon
# ============================================================
def resolve_dns(target: str) -> List[Dict[str, str]]:
    """Perform DNS resolution for target."""
    results = []
    try:
        answers = socket.getaddrinfo(target, None, socket.AF_INET, socket.SOCK_STREAM)
        seen = set()
        for ans in answers:
            ip = ans[4][0]
            if ip not in seen:
                seen.add(ip)
                results.append({'type': 'A', 'value': ip})
    except Exception:
        pass
    # MX/NS/TXT/SOA 需 dnspython；缺失时如实标注，不再伪造 NXDOMAIN
    try:
        import dns.resolver  # noqa: F401
        has_dnspython = True
    except ImportError:
        has_dnspython = False
    if has_dnspython:
        import dns.resolver
        for rtype in ('MX', 'NS', 'TXT', 'SOA'):
            try:
                for ans in dns.resolver.query(target, rtype):
                    results.append({'type': rtype, 'value': str(ans)})
            except Exception:
                pass
    else:
        for rtype in ('MX', 'NS', 'TXT', 'SOA'):
            results.append({'type': rtype, 'value': 'N/A (dnspython not installed)'})
    return results


# ============================================================
# Capability 2: WHOIS Lookup
# ============================================================
def whois_lookup(domain: str) -> Dict[str, Any]:
    """Perform WHOIS lookup using raw socket protocol on port 43."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(('whois.verisign-grs.com', 43), timeout=5) as sock:
            sock.sendall((domain + '\r\n').encode())
            buf = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b'IANA' in buf or len(buf) > 10000:
                    break
        text = buf.decode('utf-8', errors='replace')
        parsed = {}
        for line in text.splitlines():
            if ':' in line and not line.startswith('%'):
                k, v = line.split(':', 1)
                parsed[k.strip()] = v.strip()
        return {'raw': text[:500], 'parsed': parsed, 'domain': domain}
    except Exception as e:
        return {'raw': '', 'parsed': {}, 'domain': domain, 'error': str(e)}


# ============================================================
# Capability 3: Subdomain Enumeration
# ============================================================
SUBDOMAIN_LIST = [
    'www', 'mail', 'ftp', 'admin', 'api', 'vpn', 'staging',
    'dev', 'test', 'blog', 'shop', 'status', 'cdn', 'app',
    'login', 'portal', 'support', 'docs', 'images', 'static',
    'auth', 'm', 'old', 'new', 'beta', 'demo', 'ns1', 'ns2',
]


def subdomain_enum(domain: str) -> List[Dict[str, str]]:
    """Enumerate subdomains via DNS brute force."""
    found = []
    for sub in SUBDOMAIN_LIST:
        try:
            host = f"{sub}.{domain}"
            socket.gethostbyname(host)
            found.append({'subdomain': host, 'resolved': True})
        except socket.gaierror:
            found.append({'subdomain': host, 'resolved': False})
    return found


# ============================================================
# Capability 4: Port Scan
# ============================================================
def check_port(host: str, port: int, timeout: int = 1) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def scan_common_ports(target: str, ports: Optional[List[int]] = None) -> Dict[int, bool]:
    """Scan common ports on target (thread-pool concurrent)."""
    if ports is None:
        ports = [21, 22, 25, 53, 80, 110, 143, 443, 993, 995,
                 3306, 3389, 5432, 8080, 8443, 9090]
    results = {}
    with ThreadPoolExecutor(max_workers=min(32, len(ports))) as pool:
        futures = {pool.submit(check_port, target, p): p for p in ports}
        for fut in futures:
            results[futures[fut]] = fut.result()
    return results


# ============================================================
# Capability 5: Technology Identification
# ============================================================
def identify_technology(url: str) -> Dict[str, List[str]]:
    """Identify web technologies from URL."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    found = {'headers': [], 'meta': [], 'scripts': []}
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            body = resp.read(50000).decode('utf-8', errors='replace')
            for h, v in resp.headers.items():
                if h.lower() in ('server', 'x-powered-by', 'x-frame-options', 'strict-transport-security'):
                    found['headers'].append(f"{h}: {v}")
            low = body.lower()
            patterns = [
                ('wordpress', 'WordPress'), ('jquery', 'jQuery'),
                ('react', 'React'), ('vue', 'Vue.js'), ('angular', 'Angular'),
                ('next.js', 'Next.js'), ('gatsby', 'Gatsby'),
                ('php', 'PHP'), ('django', 'Django'), ('flask', 'Flask'),
                ('nginx', 'Nginx'), ('apache', 'Apache'),
            ]
            for pat, name in patterns:
                if pat in low:
                    found['scripts'].append(name)
    except Exception as e:
        found['_error'] = str(e)
    return found


# ============================================================
# Capability 6: Email Verification
# ============================================================
def email_verify(email: str) -> Dict[str, Any]:
    """Validate email address format and check domain MX record."""
    return validate_email(email)


def validate_email(email: str) -> Dict[str, Any]:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    valid = bool(re.match(pattern, email))
    domain = email.split('@')[1] if '@' in email else ''
    mx = _get_mx(domain)
    # MX 不可用（含 dnspython 缺失）时，不把邮箱判为不可达，如实标注
    if mx is None:
        return {
            'email': email,
            'valid_format': valid,
            'domain': domain,
            'mx_record': None,
            'deliverable': None,  # unknown：MX 校验不可用
        }
    return {
        'email': email,
        'valid_format': valid,
        'domain': domain,
        'mx_record': mx,
        'deliverable': valid and mx is not None,
    }


def _get_mx(domain: str) -> Optional[str]:
    """Get MX record for domain."""
    try:
        
        records = dns.resolver.query(domain, 'MX')
        return str(records[0].exchange).rstrip('.')
    except ImportError:
        try:
            records = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_UDP)
            return None
        except Exception:
            return None
    except Exception:
        return None


# ============================================================
# Capability 7: IP Geolocation
# ============================================================
def ip_geo(ip: str) -> Dict[str, Any]:
    """Get geolocation data for an IP using ipinfo.io API."""
    try:
        req = urllib.request.Request(
            f"https://ipinfo.io/{ip}/json",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        return {
            'ip': data.get('ip', ip),
            'city': data.get('city', ''),
            'region': data.get('region', ''),
            'country': data.get('country', ''),
            'loc': data.get('loc', ''),
            'org': data.get('org', ''),
        }
    except Exception:
        return {'ip': ip, 'error': 'Geolocation service unavailable'}


# ============================================================
# Capability 8: Social Search
# ============================================================
SOCIAL_URLS = {
    'twitter': 'https://twitter.com/{}',
    'facebook': 'https://facebook.com/{}',
    'instagram': 'https://instagram.com/{}',
    'linkedin': 'https://linkedin.com/in/{}',
    'github': 'https://github.com/{}',
    'reddit': 'https://reddit.com/user/{}',
}


def social_search(target: str) -> Dict[str, Dict[str, bool]]:
    """Check if target username exists on major social platforms.

    注：多数平台有登录墙/反爬，200 只能作为“可公开访问”信号而非确定存在；
    404 视为不存在，其余状态/异常标记为 unknown（不伪造结论）。
    """
    results = {}
    ctx = ssl.create_default_context()
    for platform, url_tpl in SOCIAL_URLS.items():
        url = url_tpl.format(target)
        status = 'unknown'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                if resp.status == 200:
                    status = 'exists'
        except urllib.error.HTTPError as e:
            if e.code == 404:
                status = 'not_found'
        except Exception:
            status = 'unknown'
        results[platform] = {'status': status, 'url': url}
    return results


# ============================================================
# Full Scan Pipeline
# ============================================================
def scan_target(target: str, allow_private: bool = False) -> List[OSINTResult]:
    """Run full OSINT scan on target.

    默认拒绝本机/内网/保留地址（allow_private=True 可显式放行，用于自有资产）。
    """
    from .guard import guard_target
    guard_target(target, allow_private=allow_private)

    results = []
    is_ip = bool(re.match(r'^\d+\.\d+\.\d+\.\d+$', target))

    # 1. DNS resolution
    dns_data = resolve_dns(target)
    results.append(OSINTResult(target, 'dns', dns_data, 0.9))

    # 2. WHOIS lookup (only for domains)
    if not is_ip:
        whois_data = whois_lookup(target)
        results.append(OSINTResult(target, 'whois', whois_data, 0.85))

    # 3. Subdomain enumeration (only for domains)
    if not is_ip:
        subs = subdomain_enum(target)
        resolved_subs = [s for s in subs if s.get('resolved')]
        results.append(OSINTResult(target, 'subdomains', {'found': len(resolved_subs), 'total': len(subs), 'subs': resolved_subs}, 0.75))

    # 4. Port scan
    ports = scan_common_ports(target)
    open_ports = [p for p, up in ports.items() if up]
    results.append(OSINTResult(target, 'ports', {'open': open_ports, 'total_scanned': len(ports)}, 0.8))

    # 5. Technology identification (only for URLs/domains)
    if not is_ip:
        tech = identify_technology(target)
        results.append(OSINTResult(target, 'technology', tech, 0.7))

    # 6. IP geolocation (resolve IP first, then geolocate)
    ip_val = None
    for rec in dns_data:
        if rec.get('type') == 'A':
            ip_val = rec.get('value')
            break
    if ip_val:
        geo = ip_geo(ip_val)
        results.append(OSINTResult(target, 'geolocation', geo, 0.6))
    elif is_ip:
        geo = ip_geo(target)
        results.append(OSINTResult(target, 'geolocation', geo, 0.6))

    # 7. Email verification - test common corporate emails for domain targets
    if not is_ip:
        common_emails = [
            f"admin@{target}", f"info@{target}", f"contact@{target}",
            f"support@{target}", f"webmaster@{target}", f"postmaster@{target}",
        ]
        email_results = []
        for email in common_emails:
            v = validate_email(email)
            if v['deliverable'] is not False and v.get('mx_record'):
                email_results.append(v)
        results.append(OSINTResult(target, 'email', {'tested': common_emails, 'deliverable': email_results}, 0.5))

    # 8. Social search (only for non-IP targets)
    if not is_ip:
        social = social_search(target.split('.')[0])
        results.append(OSINTResult(target, 'social', social, 0.5))

    return results


# ============================================================
# Scanner Class
# ============================================================
class AutoclawScanner:
    """Main scanner class for GBT小土豆V8 OSINT."""

    def __init__(self, target: str, allow_private: bool = False):
        self.target = target
        self.allow_private = allow_private
        self.results: List[OSINTResult] = []

    def run(self) -> List[OSINTResult]:
        """Run full OSINT scan."""
        self.results = scan_target(self.target, allow_private=self.allow_private)
        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """Get scan summary."""
        source_counts = defaultdict(int)
        for r in self.results:
            source_counts[r.source] += 1
        return {
            'target': self.target,
            'sources_scanned': dict(source_counts),
            'total_results': len(self.results),
            'results': [r.to_dict() for r in self.results],
        }


# Backward-compatible aliases
OSINTScanner = AutoclawScanner
ScanResult = OSINTResult


def get_capability(name: str) -> Optional[Dict[str, str]]:
    """Get a specific capability by name."""
    for cap in get_available_capabilities():
        if cap['name'] == name:
            return cap
    return None
