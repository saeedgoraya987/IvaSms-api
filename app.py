#Copyright @Arslan-MD
#Updates Channel t.me/arslanmd
from flask import Flask, request, jsonify
from datetime import datetime
import cloudscraper
import json
from bs4 import BeautifulSoup
import logging
import os
import gzip
from io import BytesIO

# Brotli - try multiple imports
try:
    import brotlicffi as brotli
    BROTLI_AVAILABLE = True
except ImportError:
    try:
        import brotli
        BROTLI_AVAILABLE = True
    except ImportError:
        BROTLI_AVAILABLE = False
        brotli = None
        print("[WARNING] brotli/brotlicffi not installed. Brotli decompression disabled.")

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

class IVASSMSClient:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
            delay=10
        )
        self.base_url = "https://www.ivasms.com"
        self.logged_in = False
        self.csrf_token = None
        
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'sec-ch-ua': '"Chromium";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
        })

    def decompress_response(self, response):
        """Decompress response content if encoded with gzip or brotli."""
        encoding = response.headers.get('Content-Encoding', '').lower()
        content = response.content
        
        try:
            if encoding == 'gzip':
                logger.debug("Decompressing gzip response")
                content = gzip.decompress(content)
            elif encoding == 'br':
                if not BROTLI_AVAILABLE:
                    logger.warning("Brotli not available, using raw content")
                else:
                    logger.debug("Decompressing brotli response")
                    try:
                        # Try brotlicffi first
                        content = brotli.decompress(content)
                    except Exception as e1:
                        try:
                            # Fall back to standard brotli
                            import brotli as brotli_std
                            content = brotli_std.decompress(content)
                        except Exception as e2:
                            logger.warning(f"Brotli decompression failed: {e1} / {e2}")
                            # Use raw content as fallback
            
            return content.decode('utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            # Last resort: return raw text
            try:
                return response.text
            except:
                return str(content)

    def load_cookies(self, file_path="cookies.json"):
        """Load cookies from COOKIE_STRING env var, COOKIES_JSON env var, or file."""
        cookies = {}
        
        # Method 1: COOKIE_STRING env var (highest priority)
        cookie_string = os.getenv("COOKIE_STRING", "cf_clearance=9JN5lQXZ67diZ.4gf1RKlCmEkyDz6LS_KAVo6nuDDc4-1780374810-1.2.1.1-9ea40THqKmgtvIaxpw0.MF1Q0hG7m4UiSWZP9C4Ct3Qgi4UC0kkImsC6I9Uu6DhbBZfiisiBVvo7VoLyRXqMHuFoCeUdUxTWZm5V4FQVk.Xh_.o98ErN2iSUPSQ1Gnv7IFMFcQV8hBxurPLrgz6Ou3DaW1u4OTtPDFyl0yYcLtlPHEyfcjS_BuGsVt.ihqAnRnMig5pBFKQ84pX.r4v0OsOASuHRY_NMdcc848wiavxVAS9QJf7hxLznp1ni3nz6o.MJgeIxnCi7ft713G8Q7BlYGcQiRcuoXhO.gTYo79sIvhqqonKjlrJ.M2WJ01eKKUf1V7xM5JAhQmbIds3jMhq8sWfBx6L3wzVAy2SmBTpOiRmk2AK36Rdttun6YvKpgHvM7HuEiriLzHLWkVCxeSF9i0LVklFf1FiFQSq0.Mo; _fbp=fb.1.1770522461692.593209573323242597; XSRF-TOKEN=eyJpdiI6Im5tZ0xNZDdRTWNkcGNIZ2ZZRVIzeGc9PSIsInZhbHVlIjoiaExUbVFWaW9XN0pnUzBOYmptc2owM1RDWFVybFFtT2ZTdGN6YzRtODZna28rcWFkYUpxRWRaN1lvZVJLMjcvUU5yamtkam5ydVF3MWY1c08vK0N1NlEzVTU4ZG5CVkxPV3l4ZkVQRDl0bmRlUVozZGxMZHJkcXhtbklxbmdlMnkiLCJtYWMiOiJkZWQ1MmUzMzJiMTM2NTA5ODkwMGFiMjQ1NGUwNjY4MDk2MDc4MmUwZmExYWQ0NjJjMTM5ZTUxZmFhZDFmMzQ2IiwidGFnIjoiIn0=; ivas_sms_session=eyJpdiI6ImF0SzN4VXhyNlR3MWNFU0NmaG5vUHc9PSIsInZhbHVlIjoiQURqZWo5TVlwVWpPWWhEakhraStibmlKOURSZGlsd25tdUwyWHNGYkdkei94bzlJKzRhaUhXc0wwM2hwNmdKWjJzd0lJR3pBeitPQTlPOW4va1VhRXp3bGNLNGpKcjRQbi85MnVKUWpUZVdHY25VZm5CamN4eEo2YklOZWpybUMiLCJtYWMiOiJkN2RmNmExODczNWE0YjQxYjMzMDQwNGJkYTU1ZTM0MDBiODE4NDI1ZDJmYTUzMTFhZTI5M2MyNGVhOTliNmM1IiwidGFnIjoiIn0=")
        if cookie_string:
            logger.info("Loading cookies from COOKIE_STRING environment variable")
            for pair in cookie_string.split(';'):
                pair = pair.strip()
                if '=' in pair:
                    name, value = pair.split('=', 1)
                    cookies[name.strip()] = value.strip()
            if cookies:
                logger.info(f"✅ Loaded {len(cookies)} cookies from COOKIE_STRING")
                return cookies
        
        # Method 2: COOKIES_JSON env var
        cookies_json = os.getenv("COOKIES_JSON", "")
        if cookies_json:
            logger.info("Loading cookies from COOKIES_JSON environment variable")
            try:
                cookies_raw = json.loads(cookies_json)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in COOKIES_JSON: {e}")
                cookies_raw = None
        else:
            # Method 3: cookies.json file
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        cookies_raw = json.load(file)
                        logger.info(f"Loading cookies from {file_path}")
                else:
                    logger.error(f"Cookie file not found: {file_path}")
                    return None
            except Exception as e:
                logger.error(f"Error loading cookies file: {e}")
                return None
        
        # Parse cookies from JSON
        if 'cookies_raw' in locals() and cookies_raw:
            if isinstance(cookies_raw, dict):
                cookies = cookies_raw
                logger.info(f"✅ Loaded {len(cookies)} cookies (dict)")
            elif isinstance(cookies_raw, list):
                for cookie in cookies_raw:
                    if 'name' in cookie and 'value' in cookie:
                        cookies[cookie['name']] = cookie['value']
                logger.info(f"✅ Loaded {len(cookies)} cookies (list)")
            else:
                logger.error("Unsupported cookie format")
                return None
        
        return cookies if cookies else None

    def login_with_cookies(self, cookies_file="cookies.json"):
        """Login using cookies from env var or file."""
        logger.info("=" * 50)
        logger.info("🔐 Cookie-based authentication")
        logger.info("=" * 50)
        
        cookies = self.load_cookies(cookies_file)
        if not cookies:
            logger.error("❌ No valid cookies found!")
            return False
        
        # Set cookies in session
        for name, value in cookies.items():
            self.scraper.cookies.set(name, value, domain=".ivasms.com")
        
        logger.info(f"🍪 {len(cookies)} cookies set")
        
        try:
            # Test portal access
            logger.info("Testing portal access...")
            response = self.scraper.get(
                f"{self.base_url}/portal",
                timeout=15,
                allow_redirects=True
            )
            
            # Check for redirect to login
            if 'login' in response.url.lower():
                logger.error(f"❌ Redirected to login: {response.url}")
                return False
            
            html_content = self.decompress_response(response)
            
            # Check for login form
            if 'Account Login' in html_content:
                logger.error("❌ Login page detected - cookies invalid!")
                with open('debug_auth_failed.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return False
            
            # Success indicators
            if any(x in html_content for x in ['Saeed Ahmed', 'Dashboard', 'logout']):
                logger.info("✅ Authentication successful!")
            else:
                logger.warning("⚠️ Login status unclear, but no redirect detected")
            
            # Get CSRF token from SMS page
            logger.info("Fetching CSRF token...")
            response = self.scraper.get(
                f"{self.base_url}/portal/sms/received",
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to access SMS page: {response.status_code}")
                return False
            
            html_content = self.decompress_response(response)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract CSRF token
            csrf_token = None
            
            # Method 1: meta tag
            meta = soup.find('meta', {'name': 'csrf-token'})
            if meta and meta.get('content'):
                csrf_token = meta['content']
            
            # Method 2: hidden input
            if not csrf_token:
                inp = soup.find('input', {'name': '_token'})
                if inp and inp.get('value'):
                    csrf_token = inp['value']
            
            # Method 3: script tag
            if not csrf_token:
                import re
                for script in soup.find_all('script'):
                    if script.string and '_token' in script.string:
                        match = re.search(r'_token["\']?\s*[:=]\s*["\']([^"\']+)', script.string)
                        if match:
                            csrf_token = match.group(1)
                            break
            
            if csrf_token:
                self.csrf_token = csrf_token
                self.logged_in = True
                logger.info(f"✅ Logged in! CSRF: {csrf_token[:30]}...")
                return True
            else:
                logger.error("❌ CSRF token not found!")
                logger.error(f"HTML preview: {html_content[:500]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_otps(self, from_date="", to_date=""):
        """Fetch SMS ranges for given date range."""
        if not self.logged_in or not self.csrf_token:
            logger.error("Not logged in or no CSRF token")
            return None
        
        logger.info(f"Fetching SMS for {from_date} to {to_date or 'today'}")
        
        try:
            payload = {
                'from': from_date,
                'to': to_date,
                '_token': self.csrf_token
            }
            
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': self.csrf_token,
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/portal/sms/received"
            }
            
            response = self.scraper.post(
                f"{self.base_url}/portal/sms/received/getsms",
                data=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed: HTTP {response.status_code}")
                return None
            
            html_content = self.decompress_response(response)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract summary stats
            count_sms = '0'
            paid_sms = '0'
            unpaid_sms = '0'
            revenue_sms = '0'
            
            for selector, default in [
                ("#CountSMS", "0"), ("#PaidSMS", "0"),
                ("#UnpaidSMS", "0"), ("#RevenueSMS", "0")
            ]:
                elem = soup.select_one(selector)
                if elem:
                    val = elem.text.strip().replace(' USD', '')
                    if selector == "#CountSMS": count_sms = val
                    elif selector == "#PaidSMS": paid_sms = val
                    elif selector == "#UnpaidSMS": unpaid_sms = val
                    elif selector == "#RevenueSMS": revenue_sms = val
            
            # Extract SMS ranges - try multiple selectors
            sms_details = []
            
            # Try div.item first
            items = soup.select("div.item")
            if not items:
                # Try div.rng (alternate format)
                items = soup.select("div.rng")
            
            for item in items:
                try:
                    # Try to extract range name
                    name_elem = (
                        item.select_one(".col-sm-4") or
                        item.select_one("span.rname") or
                        item.select_one(".rname")
                    )
                    country_number = name_elem.text.strip() if name_elem else "Unknown"
                    
                    # Extract counts
                    count = "0"
                    paid = "0"
                    unpaid = "0"
                    revenue = "0"
                    
                    count_elem = item.select_one(".v-count") or item.select_one(".col-3:nth-child(2) p")
                    if count_elem:
                        count = count_elem.text.strip()
                    
                    paid_elem = item.select_one(".col-3:nth-child(3) p")
                    if paid_elem:
                        paid = paid_elem.text.strip()
                    
                    unpaid_elem = item.select_one(".col-3:nth-child(4) p")
                    if unpaid_elem:
                        unpaid = unpaid_elem.text.strip()
                    
                    rev_elem = item.select_one("span.currency_cdr") or item.select_one(".col-3:nth-child(5) p")
                    if rev_elem:
                        revenue = rev_elem.text.strip()
                    
                    sms_details.append({
                        'country_number': country_number,
                        'count': count,
                        'paid': paid,
                        'unpaid': unpaid,
                        'revenue': revenue
                    })
                except Exception as e:
                    logger.warning(f"Error parsing range item: {e}")
                    continue
            
            result = {
                'count_sms': count_sms,
                'paid_sms': paid_sms,
                'unpaid_sms': unpaid_sms,
                'revenue': revenue_sms,
                'sms_details': sms_details
            }
            
            logger.info(f"Found {len(sms_details)} ranges, {count_sms} total SMS")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching SMS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_sms_details(self, phone_range, from_date="", to_date=""):
        """Get phone numbers for a specific range."""
        if not self.logged_in or not self.csrf_token:
            return None
        
        try:
            payload = {
                '_token': self.csrf_token,
                'start': from_date,
                'end': to_date,
                'range': phone_range
            }
            
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': self.csrf_token,
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/portal/sms/received"
            }
            
            response = self.scraper.post(
                f"{self.base_url}/portal/sms/received/getsms/number",
                data=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                return None
            
            html_content = self.decompress_response(response)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            number_details = []
            
            # Try multiple selectors
            items = soup.select("div.card.card-body") or soup.select("div.nrow")
            
            for item in items:
                try:
                    # Phone number
                    phone_elem = (
                        item.select_one(".col-sm-4") or
                        item.select_one("span.nnum")
                    )
                    phone_number = phone_elem.text.strip() if phone_elem else "Unknown"
                    phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
                    
                    # Extract ID
                    id_number = ''
                    onclick = (phone_elem or item).get('onclick', '')
                    if onclick:
                        parts = onclick.split("'")
                        if len(parts) >= 4:
                            id_number = parts[3]
                    
                    number_details.append({
                        'phone_number': phone_number,
                        'count': '0',
                        'paid': '0',
                        'unpaid': '0',
                        'revenue': '0',
                        'id_number': id_number
                    })
                except Exception as e:
                    logger.warning(f"Error parsing number: {e}")
                    continue
            
            return number_details
            
        except Exception as e:
            logger.error(f"Error getting SMS details: {e}")
            return None

    def get_otp_message(self, phone_number, phone_range, from_date="", to_date=""):
        """Get OTP message for a specific phone number."""
        if not self.logged_in or not self.csrf_token:
            return None
        
        try:
            payload = {
                '_token': self.csrf_token,
                'start': from_date,
                'end': to_date,
                'Number': phone_number,
                'Range': phone_range
            }
            
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': self.csrf_token,
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/portal/sms/received"
            }
            
            response = self.scraper.post(
                f"{self.base_url}/portal/sms/received/getsms/number/sms",
                data=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                return None
            
            html_content = self.decompress_response(response)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try multiple selectors for message
            for selector in [".msg-text", ".col-9.col-sm-6 p", "td p", "tbody tr td:last-child"]:
                elem = soup.select_one(selector)
                if elem:
                    return elem.text.strip()
            
            # Try to find any text in tbody
            tbody = soup.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                if rows:
                    last_row = rows[-1]
                    tds = last_row.find_all('td')
                    if len(tds) >= 2:
                        return tds[-1].get_text(strip=True)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting OTP message: {e}")
            return None

    def get_all_otp_messages(self, sms_details, from_date="", to_date="", limit=None):
        """Get all OTP messages from the list of ranges."""
        all_otp_messages = []
        
        logger.info(f"Processing {len(sms_details)} ranges (limit: {limit or 'none'})")
        
        for detail in sms_details:
            phone_range = detail.get('country_number', '')
            if not phone_range or phone_range == 'Unknown':
                continue
            
            number_details = self.get_sms_details(phone_range, from_date, to_date)
            
            if number_details:
                for number_detail in number_details:
                    if limit is not None and len(all_otp_messages) >= limit:
                        logger.info(f"Reached limit of {limit}")
                        return all_otp_messages
                    
                    phone_number = number_detail.get('phone_number', '')
                    if not phone_number:
                        continue
                    
                    otp_message = self.get_otp_message(
                        phone_number, phone_range, from_date, to_date
                    )
                    
                    if otp_message:
                        all_otp_messages.append({
                            'range': phone_range,
                            'phone_number': phone_number,
                            'otp_message': otp_message
                        })
        
        logger.info(f"Collected {len(all_otp_messages)} OTP messages")
        return all_otp_messages


# ==================== FLASK APP ====================
app = Flask(__name__)
client = IVASSMSClient()

with app.app_context():
    logger.info("=" * 60)
    logger.info("🚀 IVAS SMS API Starting")
    logger.info("=" * 60)
    
    if client.login_with_cookies():
        logger.info("✅ Client initialized successfully")
    else:
        logger.error("❌ Client initialization failed!")
        logger.error("Set COOKIE_STRING env var with valid cookies")


@app.route('/')
def welcome():
    return jsonify({
        'message': 'IVAS SMS API',
        'status': 'running',
        'authenticated': client.logged_in,
        'endpoints': {
            '/sms?date=DD/MM/YYYY&limit=10': 'Get OTP messages',
            '/status': 'Check auth status',
            '/debug': 'Debug raw HTML'
        }
    })


@app.route('/status')
def status():
    return jsonify({
        'authenticated': client.logged_in,
        'csrf_token': client.csrf_token[:30] + '...' if client.csrf_token else None,
        'broti_available': BROTLI_AVAILABLE
    })


@app.route('/debug')
def debug():
    """Debug endpoint to see raw SMS data."""
    if not client.logged_in:
        client.login_with_cookies()
    
    if not client.csrf_token:
        return jsonify({'error': 'No CSRF token'}), 500
    
    from_date = request.args.get('date', '')
    
    try:
        payload = {'from': from_date, 'to': '', '_token': client.csrf_token}
        headers = {
            'Accept': 'text/html, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-TOKEN': client.csrf_token,
        }
        
        r = client.scraper.post(
            f"{client.base_url}/portal/sms/received/getsms",
            data=payload, headers=headers, timeout=30
        )
        
        html = client.decompress_response(r)
        
        return jsonify({
            'status_code': r.status_code,
            'html_length': len(html),
            'has_items': 'item' in html or 'rng' in html,
            'item_count': html.count('class="item"') + html.count('class="rng"'),
            'html_preview_1000': html[:1000],
            'html_preview_last_1000': html[-1000:] if len(html) > 1000 else ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sms')
def get_sms():
    if not client.logged_in:
        logger.warning("Re-authenticating...")
        if not client.login_with_cookies():
            return jsonify({'error': 'Authentication failed. Update cookies.'}), 401
    
    date_str = request.args.get('date')
    limit = request.args.get('limit')
    
    if not date_str:
        return jsonify({'error': 'Date required: DD/MM/YYYY'}), 400
    
    try:
        datetime.strptime(date_str, '%d/%m/%Y')
        from_date = date_str
        to_date = request.args.get('to_date', '')
        if to_date:
            datetime.strptime(to_date, '%d/%m/%Y')
    except ValueError:
        return jsonify({'error': 'Invalid date. Use DD/MM/YYYY'}), 400
    
    if limit:
        try:
            limit = int(limit)
            if limit <= 0:
                return jsonify({'error': 'Limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Limit must be integer'}), 400
    else:
        limit = None
    
    logger.info(f"📱 SMS request: {from_date} limit={limit}")
    
    result = client.check_otps(from_date=from_date, to_date=to_date)
    
    if not result:
        return jsonify({'error': 'Failed to fetch SMS data'}), 500
    
    otp_messages = client.get_all_otp_messages(
        result.get('sms_details', []),
        from_date=from_date,
        to_date=to_date,
        limit=limit
    )
    
    return jsonify({
        'status': 'success',
        'from_date': from_date,
        'to_date': to_date or 'Not specified',
        'limit': limit if limit else 'Not specified',
        'sms_stats': {
            'count_sms': result['count_sms'],
            'paid_sms': result['paid_sms'],
            'unpaid_sms': result['unpaid_sms'],
            'revenue': result['revenue']
        },
        'otp_messages': otp_messages,
        'total_otps': len(otp_messages)
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
