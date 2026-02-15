"""
Medical Search Engine Module

Provides LLM-powered web search capabilities for retrieving precise medical information
from authoritative sources including CPT codes, ICD-10 codes, and insurance policy criteria.

Uses Tavily API for optimized search results.
"""

import os
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CPTCodeInfo(BaseModel):
    """CPT code information from authoritative sources"""
    code: str = Field(..., description="CPT code number")
    description: str = Field(..., description="Official procedure description")
    typical_indications: List[str] = Field(default_factory=list, description="Common medical indications")
    source_url: Optional[str] = Field(None, description="Source URL for reference")
    retrieved_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of retrieval")


class ICD10CodeInfo(BaseModel):
    """ICD-10 code information from authoritative sources"""
    code: str = Field(..., description="ICD-10 code")
    description: str = Field(..., description="Official diagnosis description")
    category: Optional[str] = Field(None, description="ICD-10 category")
    source_url: Optional[str] = Field(None, description="Source URL for reference")
    retrieved_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of retrieval")


class PolicyCriteria(BaseModel):
    """Insurance policy coverage criteria"""
    procedure: str = Field(..., description="Procedure name")
    payer: str = Field(..., description="Insurance payer name")
    coverage_criteria: List[str] = Field(default_factory=list, description="Coverage requirements")
    prior_auth_required: Optional[bool] = Field(None, description="Whether prior authorization is required")
    source_url: Optional[str] = Field(None, description="Policy document URL")
    retrieved_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of retrieval")


class SearchCache:
    """Simple file-based cache for search results"""
    
    def __init__(self, cache_dir: str = ".search_cache", ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> str:
        """Get cache file path for a given key"""
        safe_key = key.replace("/", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def get(self, key: str) -> Optional[dict]:
        """Retrieve cached result if not expired"""
        cache_path = self._get_cache_path(key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            
            # Check if expired
            cached_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cached_time > self.ttl:
                os.remove(cache_path)
                return None
            
            return cached['data']
        except Exception as e:
            logger.warning(f"Cache read error for {key}: {e}")
            return None
    
    def set(self, key: str, data: dict):
        """Store result in cache"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }, f)
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")


class MedicalSearchEngine:
    """
    LLM-powered search engine for medical information
    
    Retrieves precise data from authoritative sources:
    - CPT code descriptions from AAPC, CMS
    - ICD-10 code information from official databases
    - Insurance policy criteria from payer websites
    """
    
    def __init__(self, api_key: Optional[str] = None, enable_cache: bool = True):
        """
        Initialize search engine
        
        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY env var)
            enable_cache: Whether to cache search results
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.enabled = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"
        self.cache = SearchCache() if enable_cache else None
        
        if self.enabled and not self.api_key:
            logger.warning("Web search enabled but TAVILY_API_KEY not set. Search will be disabled.")
            self.enabled = False
        
        # Initialize Tavily client only if enabled and API key is available
        self.client = None
        if self.enabled:
            try:
                from tavily import TavilyClient
                self.client = TavilyClient(api_key=self.api_key)
                logger.info("Tavily search engine initialized successfully")
            except ImportError:
                logger.error("tavily-python not installed. Run: pip install tavily-python")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
                self.enabled = False
    
    def search_cpt_code(self, cpt_code: str) -> Optional[CPTCodeInfo]:
        """
        Search for official CPT code description and guidelines
        
        Args:
            cpt_code: CPT code number (e.g., "50360")
        
        Returns:
            CPTCodeInfo object or None if search fails
        """
        if not self.enabled:
            logger.debug("Web search disabled, skipping CPT lookup")
            return None
        
        # Check cache first
        cache_key = f"cpt_{cpt_code}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.info(f"CPT {cpt_code} retrieved from cache")
                return CPTCodeInfo(**cached)
        
        try:
            query = f"CPT code {cpt_code} description medical billing procedure"
            logger.info(f"Searching for CPT {cpt_code}...")
            
            results = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_domains=["aapc.com", "cms.gov", "ama-assn.org", "icd10data.com"]
            )
            
            # Parse results
            if results and 'results' in results and len(results['results']) > 0:
                top_result = results['results'][0]
                
                cpt_info = CPTCodeInfo(
                    code=cpt_code,
                    description=self._extract_cpt_description(top_result['content'], cpt_code),
                    typical_indications=self._extract_indications(top_result['content']),
                    source_url=top_result.get('url')
                )
                
                # Cache the result
                if self.cache:
                    self.cache.set(cache_key, cpt_info.model_dump())
                
                logger.info(f"CPT {cpt_code} found: {cpt_info.description[:50]}...")
                return cpt_info
            
            logger.warning(f"No results found for CPT {cpt_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching CPT {cpt_code}: {e}")
            return None
    
    def search_icd10_code(self, icd_code: str) -> Optional[ICD10CodeInfo]:
        """
        Search for official ICD-10 code description
        
        Args:
            icd_code: ICD-10 code (e.g., "N18.6")
        
        Returns:
            ICD10CodeInfo object or None if search fails
        """
        if not self.enabled:
            logger.debug("Web search disabled, skipping ICD-10 lookup")
            return None
        
        # Check cache first
        cache_key = f"icd_{icd_code}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.info(f"ICD-10 {icd_code} retrieved from cache")
                return ICD10CodeInfo(**cached)
        
        try:
            query = f"ICD-10 code {icd_code} description diagnosis"
            logger.info(f"Searching for ICD-10 {icd_code}...")
            
            results = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_domains=["icd10data.com", "cms.gov", "who.int"]
            )
            
            # Parse results
            if results and 'results' in results and len(results['results']) > 0:
                top_result = results['results'][0]
                
                icd_info = ICD10CodeInfo(
                    code=icd_code,
                    description=self._extract_icd_description(top_result['content'], icd_code),
                    category=self._extract_icd_category(top_result['content']),
                    source_url=top_result.get('url')
                )
                
                # Cache the result
                if self.cache:
                    self.cache.set(cache_key, icd_info.model_dump())
                
                logger.info(f"ICD-10 {icd_code} found: {icd_info.description[:50]}...")
                return icd_info
            
            logger.warning(f"No results found for ICD-10 {icd_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching ICD-10 {icd_code}: {e}")
            return None
    
    def search_policy_criteria(self, procedure: str, payer: str = "Medicare") -> Optional[PolicyCriteria]:
        """
        Search for insurance policy coverage criteria
        
        Args:
            procedure: Procedure name or CPT code
            payer: Insurance payer name (default: Medicare)
        
        Returns:
            PolicyCriteria object or None if search fails
        """
        if not self.enabled:
            logger.debug("Web search disabled, skipping policy lookup")
            return None
        
        # Check cache first
        cache_key = f"policy_{payer}_{procedure}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.info(f"Policy for {procedure} ({payer}) retrieved from cache")
                return PolicyCriteria(**cached)
        
        try:
            query = f"{payer} prior authorization coverage criteria {procedure}"
            logger.info(f"Searching for policy: {payer} - {procedure}...")
            
            results = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=5
            )
            
            # Parse results
            if results and 'results' in results and len(results['results']) > 0:
                top_result = results['results'][0]
                
                policy_info = PolicyCriteria(
                    procedure=procedure,
                    payer=payer,
                    coverage_criteria=self._extract_criteria(top_result['content']),
                    prior_auth_required=self._check_prior_auth(top_result['content']),
                    source_url=top_result.get('url')
                )
                
                # Cache the result
                if self.cache:
                    self.cache.set(cache_key, policy_info.model_dump())
                
                logger.info(f"Policy found for {procedure} ({payer})")
                return policy_info
            
            logger.warning(f"No policy found for {procedure} ({payer})")
            return None
            
        except Exception as e:
            logger.error(f"Error searching policy for {procedure}: {e}")
            return None
    
    # Helper methods for parsing search results
    
    def _extract_cpt_description(self, content: str, cpt_code: str) -> str:
        """Extract CPT description from search result content"""
        # Simple extraction - look for the code followed by description
        lines = content.split('\n')
        for line in lines:
            if cpt_code in line and '-' in line:
                parts = line.split('-', 1)
                if len(parts) > 1:
                    return parts[1].strip()[:200]  # Limit to 200 chars
        
        # Fallback: return first sentence
        sentences = content.split('.')
        return sentences[0].strip()[:200] if sentences else "Description not found"
    
    def _extract_icd_description(self, content: str, icd_code: str) -> str:
        """Extract ICD-10 description from search result content"""
        lines = content.split('\n')
        for line in lines:
            if icd_code in line and '-' in line:
                parts = line.split('-', 1)
                if len(parts) > 1:
                    return parts[1].strip()[:200]
        
        sentences = content.split('.')
        return sentences[0].strip()[:200] if sentences else "Description not found"
    
    def _extract_icd_category(self, content: str) -> Optional[str]:
        """Extract ICD-10 category from search result"""
        # Look for category mentions
        if "category" in content.lower():
            lines = content.split('\n')
            for line in lines:
                if "category" in line.lower():
                    return line.strip()[:100]
        return None
    
    def _extract_indications(self, content: str) -> List[str]:
        """Extract typical indications from CPT search result"""
        indications = []
        keywords = ["indication", "used for", "performed for", "treatment of"]
        
        lines = content.split('.')
        for line in lines:
            if any(keyword in line.lower() for keyword in keywords):
                indications.append(line.strip()[:150])
                if len(indications) >= 3:
                    break
        
        return indications
    
    def _extract_criteria(self, content: str) -> List[str]:
        """Extract coverage criteria from policy search result"""
        criteria = []
        keywords = ["criteria", "requirement", "must", "should", "documented"]
        
        lines = content.split('.')
        for line in lines:
            if any(keyword in line.lower() for keyword in keywords):
                criteria.append(line.strip()[:150])
                if len(criteria) >= 5:
                    break
        
        return criteria
    
    def _check_prior_auth(self, content: str) -> Optional[bool]:
        """Check if prior authorization is mentioned"""
        if "prior authorization required" in content.lower():
            return True
        elif "no prior authorization" in content.lower():
            return False
        return None


# Convenience function for quick searches
def quick_search_cpt(cpt_code: str) -> Optional[CPTCodeInfo]:
    """Quick CPT code lookup"""
    engine = MedicalSearchEngine()
    return engine.search_cpt_code(cpt_code)


def quick_search_icd10(icd_code: str) -> Optional[ICD10CodeInfo]:
    """Quick ICD-10 code lookup"""
    engine = MedicalSearchEngine()
    return engine.search_icd10_code(icd_code)


if __name__ == "__main__":
    # Test the search engine
    print("Testing Medical Search Engine...")
    
    engine = MedicalSearchEngine()
    
    if engine.enabled:
        # Test CPT search
        print("\n1. Testing CPT Code Search:")
        cpt_info = engine.search_cpt_code("50360")
        if cpt_info:
            print(f"   Code: {cpt_info.code}")
            print(f"   Description: {cpt_info.description}")
            print(f"   Source: {cpt_info.source_url}")
        
        # Test ICD-10 search
        print("\n2. Testing ICD-10 Code Search:")
        icd_info = engine.search_icd10_code("N18.6")
        if icd_info:
            print(f"   Code: {icd_info.code}")
            print(f"   Description: {icd_info.description}")
            print(f"   Source: {icd_info.source_url}")
        
        # Test policy search
        print("\n3. Testing Policy Search:")
        policy_info = engine.search_policy_criteria("kidney transplant", "Medicare")
        if policy_info:
            print(f"   Procedure: {policy_info.procedure}")
            print(f"   Payer: {policy_info.payer}")
            print(f"   Criteria: {policy_info.coverage_criteria[:2]}")
    else:
        print("Search engine disabled. Set ENABLE_WEB_SEARCH=true and TAVILY_API_KEY to enable.")
