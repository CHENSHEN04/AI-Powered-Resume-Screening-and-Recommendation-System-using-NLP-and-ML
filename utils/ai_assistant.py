"""
AI Assistant Module
===================
Integrates the Resume AI Assistant with Stitch MCP Memory.
Uses distilgpt2 as a lightweight model for career coaching.
Falls back to rule-based responses if model loading fails.
"""

import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# Rule-Based Fallback (Always Works)
# ==============================================================================
class RuleBasedCoach:
    """Simple rule-based career coach that works without any ML model."""
    
    RESPONSES = {
        "skill": "Based on your resume, I recommend focusing on building the skills listed in your Skill Gaps tab. Start with the required ones first, then move to recommended skills.",
        "interview": "For interview preparation: 1) Review the job description carefully, 2) Prepare STAR-format examples for each required skill, 3) Practice coding/technical problems related to your target role.",
        "resume": "Resume tips: 1) Use action verbs and quantify achievements, 2) Tailor your resume for each application, 3) Keep it to 1-2 pages, 4) Include relevant keywords from the job description.",
        "career": "Career advice: 1) Build a strong portfolio on GitHub, 2) Network on LinkedIn, 3) Consider certifications in your gap areas, 4) Look for internship/project opportunities to gain practical experience.",
        "salary": "Salary research: Check Glassdoor, Levels.fyi, and Payscale for your target role and location. Consider total compensation including benefits.",
        "learn": "For learning new skills: 1) Start with free resources (YouTube, freeCodeCamp), 2) Build small projects to practice, 3) Get certified on Coursera or Udemy, 4) Contribute to open source projects.",
        "gap": "To close your skill gaps: Focus on one skill at a time from the 'Missing Required' list. Dedicate 1-2 hours daily. Build a mini-project using each new skill to solidify your understanding.",
        "default": "I can help with: skill development, interview prep, resume tips, career guidance, learning paths, and salary insights. Ask me anything about your career path!"
    }
    
    def generate_response(self, query: str, user_id: str = "") -> str:
        query_lower = query.lower()
        for keyword, response in self.RESPONSES.items():
            if keyword in query_lower:
                return response
        return self.RESPONSES["default"]


# ==============================================================================
# Model-Based AI Assistant
# ==============================================================================
@st.cache_resource(show_spinner="Loading AI Brain... (First run may take time)")
def load_model_pipeline(model_name: str):
    """
    Load the model and tokenizer. Cached by Streamlit to avoid reloading.
    """
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
        
        logger.info(f"Loading model: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Use GPU if available, otherwise CPU
        device_type = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device_type}")
        
        dtype = torch.float16 if device_type == "cuda" else torch.float32
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map="auto" if device_type == "cuda" else None
        )
        
        if device_type == "cpu":
            model = model.to("cpu")
            
        # Set pad token if missing
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            
        generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=150,
            do_sample=True,
            temperature=0.7,
            repetition_penalty=1.2
        )
        return generator
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


class AIAssistant:
    """
    AI Career Coach with model-based generation + rule-based fallback.
    """
    
    def __init__(self, model_name: str = "distilgpt2"):
        self.model_name = model_name
        self.fallback = RuleBasedCoach()
        self.generator = None
        
        # Try loading the Stitch MCP client (optional)
        try:
            from utils.mcp_client import StitchClient
            self.stitch = StitchClient()
        except Exception:
            self.stitch = None
        
        # Try loading the ML model
        try:
            self.generator = load_model_pipeline(self.model_name)
        except Exception as e:
            logger.warning(f"Model loading failed, using rule-based fallback: {e}")

    def generate_response(self, user_query: str, user_id: str) -> str:
        """
        Generate a response. Uses ML model if available, falls back to rules.
        """
        # If no model loaded, use rule-based fallback
        if not self.generator:
            return self.fallback.generate_response(user_query, user_id)

        # 1. Retrieve Context from Stitch (optional)
        context_str = ""
        if self.stitch:
            try:
                self.stitch.set_session(user_id)
                memories = self.stitch.retrieve_context(user_query)
                if memories:
                    context_str = "Context: " + " | ".join(
                        [m for m in memories if isinstance(m, str)]
                    )
            except Exception:
                pass  # Stitch is optional

        # 2. Construct Prompt
        prompt = f"Career Coach Question: {user_query}\n{context_str}\nAdvice:"

        # 3. Generate
        try:
            output = self.generator(prompt, return_full_text=False)
            response = output[0]['generated_text'].strip()
            
            # If response is too short or garbled, use fallback
            if len(response) < 10:
                return self.fallback.generate_response(user_query, user_id)
            
            # 4. Store Interaction (Best Effort)
            if self.stitch:
                try:
                    self.stitch.store_memory(
                        key=f"chat_{user_id}",
                        content=f"Q: {user_query} | A: {response}",
                        metadata={"timestamp": "now"}
                    )
                except Exception as e:
                    logger.warning(f"Failed to save memory: {e}")
            
            return response
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self.fallback.generate_response(user_query, user_id)