import os
import json
import time
from datetime import datetime

class ResponseCache:
    def __init__(self, cache_dir="cache", ttl_hours=24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        os.makedirs(cache_dir, exist_ok=True)

    def _generate_cache_key(self, prompt, portfolio):
        """Generate a unique cache key based on prompt and portfolio"""
        # Convert portfolio to dict if it's a string
        if isinstance(portfolio, str):
            portfolio_dict = {}
            for line in portfolio.split('\n'):
                if '$' in line and 'in' in line:
                    parts = line.split('$')[1].split('in')
                    amount = float(parts[0].replace(',', '').strip())
                    symbol = parts[1].strip()
                    portfolio_dict[symbol] = amount
            portfolio = portfolio_dict
            
        cache_data = {
            "prompt": prompt,
            "portfolio": dict(sorted(portfolio.items()))
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return str(hash(cache_str))

    def get_cached_response(self, prompt, portfolio):
        """Get cached response if it exists and is not expired"""
        cache_key = self._generate_cache_key(prompt, portfolio)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            
            # Check if cache is still valid
            if time.time() - cached_data['timestamp'] < self.ttl_seconds:
                return cached_data['response'], cached_data['loan_metrics']
        
        return None, None

    def cache_response(self, prompt, portfolio, response, loan_metrics):
        """Cache the response and loan metrics"""
        cache_key = self._generate_cache_key(prompt, portfolio)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        cache_data = {
            'timestamp': time.time(),
            'response': response,
            'loan_metrics': loan_metrics
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)