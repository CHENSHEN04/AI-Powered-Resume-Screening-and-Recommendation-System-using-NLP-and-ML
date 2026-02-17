
"""
AI Assistant Module
===================
Integrates the Resume AI Assistant model with Stitch MCP Memory.
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from utils.mcp_client import StitchClient
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAssistant:
    """
    AI Career Coach that remembers user context via Stitch MCP.
    """
    
    def __init__(self, model_name: str = "kiritps/resume-ai-assistant"):
        self.model_name = model_name
        self.stitch = StitchClient()
        self.generator = None
        self.tokenizer = None
        

@st.cache_resource(show_spinner="Loading AI Brain... (First run may take time)")
def load_model_pipeline(model_name: str):
    """
    Load the model and tokenizer. Cached by Streamlit to avoid reloading.
    """
    try:
        logger.info(f"Loading model: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Use GPU if available, otherwise CPU
        device_type = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device_type}")
        
        # Check if float16 is supported on CPU (usually no, so force float32 for CPU)
        dtype = torch.float16 if device_type == "cuda" else torch.float32
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map="auto" if device_type == "cuda" else None
        )
        
        if device_type == "cpu":
            model = model.to("cpu")
            
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
        st.error(f"Failed to load AI model: {e}")
        return None

class AIAssistant:
    """
    AI Career Coach that remembers user context via Stitch MCP.
    """
    
    def __init__(self, model_name: str = "kiritps/resume-ai-assistant"):
        self.model_name = model_name
        self.stitch = StitchClient()
        self.generator = load_model_pipeline(self.model_name)

    def generate_response(self, user_query: str, user_id: str) -> str:
        """
        Generate a response with memory context.
        """
        if not self.generator:
            return "I'm having trouble accessing my brain (Model Error). Please check the logs."

        # 1. Retrieve Context from Stitch
        self.stitch.set_session(user_id)
        # Use a safe call in case Stitch is offline
        try:
            memories = self.stitch.retrieve_context(user_query)
        except Exception:
            memories = [] # Fallback to no memory
        
        context_str = ""
        if memories:
            context_str = "Context from previous conversations:\n" + "\n".join(
                [f"- {m}" for m in memories if isinstance(m, str)]
            )
        
        # 2. Construct Prompt
        # Simplified prompt structure for stability
        prompt = f"User: {user_query}\nContext: {context_str}\nAssistant:"

        # 3. Generate
        try:
            # Generate
            output = self.generator(prompt, return_full_text=False)
            response = output[0]['generated_text'].strip()
            
            # 4. Store Interaction (Best Effort)
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
            return "I encountered an error generating a response."
