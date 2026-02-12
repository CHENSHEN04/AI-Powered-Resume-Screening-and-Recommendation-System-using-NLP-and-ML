import re
from datetime import datetime
from typing import List, Tuple, Optional

class DateParser:
    """
    Parses dates from resume text and calculates experience durations.
    Implements conflict resolution heuristics.
    """
    
    # Regex for common date formats
    # Matches: Jan 2020, January 2020, 01/2020, 2020, Present, Current, Now
    DATE_PATTERN = r"(?i)\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4}|\d{1,2}/\d{4}|\d{4}|present|current|now)\b"
    
    def __init__(self):
        pass
        
    def extract_date_ranges(self, text: str) -> List[Tuple[datetime, datetime]]:
        """
        Extract date ranges from text chunks (e.g. "Jan 2020 - Present").
        Returns list of (start_date, end_date).
        """
        ranges = []
        # Look for "Date - Date" patterns
        # This is a simplification; robust parsing requires more context.
        # Captures: (Date) (separator) (Date)
        range_pattern = rf"({self.DATE_PATTERN})\s*(?:-|\u2013|to)\s*({self.DATE_PATTERN})"
        
        matches = re.finditer(range_pattern, text)
        for match in matches:
            start_str, end_str = match.group(1), match.group(2)
            start_date = self._parse_date_string(start_str)
            end_date = self._parse_date_string(end_str)
            
            if start_date and end_date:
                if end_date < start_date:
                    # Swap if inverted or ignore?
                    pass 
                else:
                    ranges.append((start_date, end_date))
                    
        return ranges

    def calculate_total_experience(self, text: str) -> float:
        """
        Calculate total years of experience from a text block (e.g. Work History).
        Handles overlapping ranges.
        """
        ranges = self.extract_date_ranges(text)
        if not ranges:
            return 0.0
            
        # Sort by start date
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        
        merged = []
        if sorted_ranges:
            curr_start, curr_end = sorted_ranges[0]
            for i in range(1, len(sorted_ranges)):
                next_start, next_end = sorted_ranges[i]
                
                if next_start <= curr_end: # Overlap or Touch
                    curr_end = max(curr_end, next_end)
                else:
                    merged.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            merged.append((curr_start, curr_end))
            
        total_days = sum((end - start).days for start, end in merged)
        return round(total_days / 365.25, 1)

    def resolve_experience_conflict(self, claimed_years: float, calculated_years: float, section_source: str) -> float:
        """
        Heuristic to resolve conflict between claimed vs calculated experience.
        
        Rules:
        1. If Source is 'Work Experience' (calculated), trust it over 'Summary' (claimed).
        2. If Calculated is significantly lower than Claimed (>2 years diff), flag conflict but lean towards Calculated * 1.2 (buffer for missing dates).
        3. If Calculated is 0 (parsing failed), fallback to Claimed but flag low confidence.
        """
        if calculated_years == 0:
            return claimed_years # Fallback
            
        if abs(claimed_years - calculated_years) < 1.0:
            return max(claimed_years, calculated_years) # Benefit of doubt
            
        if calculated_years < claimed_years:
            # Significant discrepancy
            # Trust calculated, but add buffer for parsing errors/gaps
            adjusted_calculated = calculated_years * 1.1
            return adjusted_calculated
            
        return calculated_years # Calculated is higher (maybe concurrent jobs), trust it.

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Convert varied date strings to datetime objects."""
        s = date_str.lower().strip()
        
        if s in ["present", "current", "now"]:
            return datetime.now()
            
        try:
            # Try formats
            # Jan 2020
            try: return datetime.strptime(s, "%b %Y")
            except: pass
            
            # January 2020
            try: return datetime.strptime(s, "%B %Y")
            except: pass
            
            # 01/2020
            try: return datetime.strptime(s, "%m/%Y")
            except: pass
            
            # 2020 (Assume Jan 1)
            try: return datetime.strptime(s, "%Y")
            except: pass
            
        except:
            return None
        return None
