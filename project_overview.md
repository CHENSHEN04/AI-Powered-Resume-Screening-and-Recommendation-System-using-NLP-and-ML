# AI-Powered Resume Screening and Recommendation System

---

## 1. Project Overview

### What is the project about?
> to address shortcomings, ATS systems relying on rules that stagnate, discriminate, and misunderstand meaning & DL/LLM are accurate but computationally intensive and lack of transparency
> this project aims to build a HYBRID resume screening and recommendation system using NLP and ML
> fill a latency versus depth gap in candidate search, synergizes statistical classification with semantic analysis

### Architecture Choice
> [!datasetused]  https://huggingface.co/datasets/ahmedheakl/resume-atlas
- 24,000+ labeled resume samples across 50+ job categories
- Structured dataset with resume text and corresponding job category labels, making it ideal for training classification models to categorize resumes by professional domain.
- This dataset can be used for:
    - **Resume Classification**: Training models to categorize resumes by job domain
    - **Skills Extraction**: Identifying technical and soft skills from resume text
    - **Job Matching**: Aligning candidates with appropriate job categories
    - **Market Analysis**: Understanding skill requirements across different industries
    - **Gap Analysis**: Identifying skill deficiencies relative to job requirements
- dataset structure
CSV format with two primary columns:
1. **Text**: Full resume content as extracted text
2. **Category**: Job category label (e.g., "Accountant", "HR", "Java Developer", "Data Science")

Example:
```
Category,Text
"Accountant","Education: Bachelor of Commerce...Skills: QuickBooks, Excel, SAP..."
"Java Developer","Experience: Software Engineer at TechCorp...Skills: Java, Spring Boot, MySQL..."
```

- data fields
- **Category**: Job category or professional domain (string)
  - Examples: "Accountant", "Advocate", "Agriculture", "Banking", "HR", "Information Technology", "Java Developer", "Python Developer", "Sales", "Testing"
- **Text**: Complete resume content as extracted/cleaned text (string)
  - Includes: Education background, work experience, skills, certifications, projects

- programming languages detected
The dataset includes mentions of various programming languages and technologies commonly found in technical resumes:

Languages: Python, Java, JavaScript, C#, C++, SQL, HTML/CSS, PHP, Ruby, Go, Rust, TypeScript
Frameworks: React, Angular, Vue, Django, Flask, Spring, .NET, Node.js
Tools: Docker, Kubernetes, AWS, Azure, GCP, Terraform, Git, Jenkins
Databases: MySQL, PostgreSQL, MongoDB, Oracle, Redis

- dataset creation
    - Curation Rationale
    This dataset was created to democratize access to professional resume writing assistance and help develop AI tools that can provide personalized career development support. It addresses the need for structured training data in the career services domain.
    - Source Data
    The dataset consists of curated resume examples and professional feedback conversations, ensuring diverse representation across:
        - Industries (Technology, Healthcare, Finance, Education, etc.)
        - Experience levels (Entry-level to Senior positions)
        - Job roles (Engineering, Management, Sales, Creative, etc.)
        - Geographic regions
    - Personal and Sensitive Information
    All personally identifiable information (PII) has been removed or anonymized:
        - Names replaced with generic placeholders
        - Contact information (emails, phones, addresses) removed
        - Company names generalized where appropriate
        - Dates anonymized to relative timeframes

- Considerations for using
    - social impact
        - Job seekers improve their resumes without expensive career services
        - Reduce barriers to professional development
        - Standardize resume quality across different backgrounds
        - Support non-native speakers in professional writing
    - Known Limitations
        - Primary focus on English-language resumes
        - May reflect certain regional or cultural resume preferences
        - Technology sector may be overrepresented
        - Resume styles evolve over time; dataset reflects current best practices
    - recommendations
    Users should:
        - Be aware of potential biases in resume styles and formats
        - Supplement with region-specific resume guidelines if needed
        - Regularly update models as resume trends change
        - Use responsibly for helping, not gatekeeping, job seekers
- citation
@dataset{heakl2024resume,
  author = {Heakl, Ahmed},
  title = {Resume Atlas Dataset},
  year = {2024},
  publisher = {HuggingFace},
  url = {https://huggingface.co/datasets/ahmedheakl/resume-atlas},
  license = {Apache 2.0}
}
- additional information
    - Maintenance
    This dataset is actively maintained. Users are encouraged to:
    Report issues via the HuggingFace discussion tab
    Suggest improvements or additions
    Share use cases and success stories
    - future work
    Planned improvements include:
    Adding more diverse industry representations
    Including resume samples in additional languages
    Creating specialized subsets for specific use cases
    Adding metadata for better filtering

> [!NOTE] **Original Specification Dataset**: The `OUTPUT_SPECIFICATION.md` originally referenced `MikePfunk28/resume-training-dataset`, which is a conversational dataset for resume critique (not suitable for classification). This implementation uses `ahmedheakl/resume-atlas` instead, which provides structured labeled data for job category classification.
notebook: 
!pip install -U transformer
# Use a pipeline as a high-level helper
from transformers import pipeline
pipe = pipeline("text-generation", model="kiritps/resume-ai-assistant")
# Load model directly
from transformers import AutoModel
model = AutoModel.from_pretrained("kiritps/resume-ai-assistant", dtype="auto")
- A specialized AI assistant fine-tuned for resume writing, career guidance, and job search support based on GPT-Neo 1.3B.
- This model is a fine-tuned for specifically optimized for resume and career-related tasks. Using LoRA (Low-Rank Adaptation) fine-tuning, it provides professional guidance on resume writing, cover letters, interview preparation, and career development while maintaining the base model's strong language generation capabilities.
    - Developed by: KIRIT P S
    - Model type: Causal Language Model (Decoder)
    - Language(s) (NLP): English
    - License: Apache 2.0
    - Specialized for: Resume writing, career guidance, job search assistance
Model Sources
- Training Dataset: ahmedheakl/resume-atlas
- Fine-tuning Method: LoRA (Low-Rank Adaptation)

- Direct Use
    - The model is designed for direct use in career-related applications:
    - Resume Writing: Generate professional summaries, describe work experience, highlight relevant skills
    - Cover Letter Creation: Write compelling cover letters tailored to specific job applications
    - Interview Preparation: Practice responses to common behavioral and technical interview questions
    - Career Advice: Receive guidance on career transitions, skill development, and job search strategies
    - Professional Communication: Improve LinkedIn profiles, networking messages, and professional correspondence

- Downstream Use
    - This model can be integrated into:
    - Career counseling platforms and job search websites
    - HR tools for resume screening and candidate assessment
    - Educational platforms for career development courses
    - Chatbots and virtual assistants focused on career guidance
    - Professional writing tools and browser extensions

- Out-of-Scope Use
    - General-purpose text generation: Not optimized for non-career related content
    - Academic writing: Not specifically trained for research papers or academic content
    - Creative writing: Limited capability for fiction, poetry, or creative storytelling
    - Technical documentation: Not specialized for software documentation or technical manuals
    - Legal or medical advice: Should not be used for professional legal or medical guidance

- Bias, Risks, and Limitations
    - Potential Biases:
        - May reflect biases present in traditional resume writing and hiring practices
        - Could favor certain industries or job roles over others based on training data
        - May inadvertently perpetuate gender, racial, or cultural biases in professional advice
    - Technical Limitations:
        - Context window limited to 512 tokens for optimal performance
        - Performance may degrade for highly specialized or niche career fields
        - Generated content requires human review and editing
        - May not reflect the most current job market trends or industry changes
    - Risk Considerations:
        - Users should not rely solely on AI-generated content for critical job applications
        - Output quality may vary depending on input specificity and context
        - May not account for individual circumstances or local job market conditions
    - Recommendations:
        - Always review and edit AI-generated content before using in actual applications
        - Combine with human expertise such as career counselors or industry professionals
        - Verify information against current industry standards and job requirements
        - Consider cultural context and local job market practices
        - Use as a starting point rather than a final solution for career documents
Training Data
The classification model was trained on ahmedheakl/resume-atlas, which contains:
- Dataset Size: 24,000+ labeled resumes
- Format: CSV with resume text and job category labels
- Content: Real-world resumes across 50+ professional domains
- Language: English
- Quality: Labeled dataset for supervised classification training

Training Procedure
Preprocessing
- Text sequences were formatted in conversational style (Human/Assistant pairs)
- Sequences truncated to maximum length of 512 tokens
- Padding tokens properly masked in loss calculation
- Data processed using 8 CPU workers for parallel processing

Training Hyperparameters
- Fine-tuning Method: LoRA (Low-Rank Adaptation)
- LoRA Rank: 32
- LoRA Alpha: 64
- LoRA Dropout: 0.1   
- Target Modules: c_attn, c_proj, c_fc
- Trainable Parameters: 15,728,640 (1.18% of total parameters)
- Training Regime: fp16 mixed precision
- Batch Size: 7 per device
- Gradient Accumulation Steps: 1
- Learning Rate: 2e-4
- Weight Decay: 0.01
- Warmup Steps: 200
- Number of Epochs: 3
- Optimizer: AdamW
- Sequence Length: 512 tokens

Speeds, Sizes, Times
- Training Time: Approximately 8-12 hours
- Hardware: Single GPU (12GB VRAM)
- Model Size: ~2.6GB (including LoRA adapters)
- Peak GPU Memory Usage: ~10GB during training
- Training Examples: 22,855 processed examples

Evaluation
- Testing Data, Factors & Metrics
- Testing Data
The model was evaluated using held-out examples from the training dataset and manual quality assessment of generated responses.

Factors
- Evaluation considered:

- Response Relevance: How well responses address the specific career question
- Professional Tone: Appropriateness of language and style for professional context
- Actionable Advice: Practical value of the guidance provided
- Factual Accuracy: Correctness of career advice and industry practices

Metrics
- Perplexity: Model's uncertainty in predicting next tokens
- Response Quality: Manual evaluation of coherence and usefulness
- Domain Relevance: Percentage of responses that stay on topic
- Professional Appropriateness: Evaluation of tone and content suitability

Results
The fine-tuned model demonstrates:

- High domain specificity: Consistently provides career-focused responses
- Professional tone: Maintains appropriate formality and expertise
- Actionable guidance: Offers specific, implementable advice
- Context awareness: Adapts responses based on user's career stage and field
Summary
The resume-ai-assistant model successfully specializes for the career-related tasks, showing strong performance in generating professional, relevant, and actionable career guidance while maintaining fluent language generation capabilities.

Model Examination
The model's attention patterns show increased focus on career-related keywords and professional terminology. LoRA adaptation successfully redirected the model's outputs toward career-specific domains without degrading general language capabilities.

Environmental Impact
Carbon emissions were minimized through efficient LoRA fine-tuning, which trains only 1.18% of parameters compared to full fine-tuning.
- Hardware Type: Single NVIDIA GPU (12GB)
- Hours used: ~10 hours
- Cloud Provider: Local training setup
- Compute Region: Not applicable
- Carbon Emitted: Estimated <5 kg CO2eq (significantly lower than full model training)

Technical Specifications
- Model Architecture and Objective
- Fine-tuning Method: LoRA (Low-Rank Adaptation)
- Objective: Causal language modeling with career domain specialization
- Parameter Count: 1.33B total parameters, 15.7M trainable
- Attention Heads: 16 per layer
- Hidden Size: 2048
- Vocabulary Size: 50,257 tokens

Compute Infrastructure
- Hardware
    - GPU: Single 12GB GPU (optimal for LoRA fine-tuning)
    - CPU: Multi-core processor for data loading (8 workers)
    - RAM: 64GB system memory
    - Storage: SSD for fast data access

- Software
    - Framework: PyTorch with Transformers library
    - Fine-tuning Library: PEFT (Parameter Efficient Fine-Tuning)
    - Precision: FP16 mixed precision training
    - Optimization: AdamW optimizer with linear warmup

Citation
BibTeX:

@misc{resume-ai-assistant-2025, title={Resume AI Assistant: A Fine-tuned GPT-Neo 1.3B for Career Guidance}, author={Individual Developer}, year={2025}, publisher={Hugging Face Model Hub}, url={https://huggingface.co/kiritps/resume-ai-assistant} }

APA: Individual Developer. (2025). Resume AI Assistant: A Fine-tuned GPT-Neo 1.3B for Career Guidance. Hugging Face Model Hub. https://huggingface.co/kiritps/resume-ai-assistant

Glossary
LoRA: Low-Rank Adaptation - A parameter-efficient fine-tuning method
PEFT: Parameter Efficient Fine-Tuning - Training only a subset of model parameters
Causal LM: Causal Language Model - Predicts next token given previous context
fp16: 16-bit floating point precision for memory efficiency

> [!currentproposal] -(Input → Processing → Output)
1. Input layer 
    - ingesting and preprocessing unstructured resume information using parsing methods which standardize multiple formatting styles
2. Hybrid Processing Layer 
    - TF-IDF and SVM are used in a hybrid way to achieve fast, keyword-based statistical classification of resumes
    - BERT is used to create deep contextually embedded representations that facilitate semantic matching
- provides the ability to achieve highly computationally efficient and fine-granularity understanding required for accurate skill alignment
```
Skill-Gap Pipeline:
1. Extract skills from resume using NER or keyword matching
2. Load job requirements from database/job description
3. Compare using:
   - Exact match for hard skills (Python, SQL)
   - Semantic similarity for soft skills (leadership ≈ management)
4. Calculate gap score and generate recommendations
```
3. Output Layer 
    - Streamlit framework is used to create an interactive web interface for users to upload and analyze their resumes
    - The interface displays the results of the hybrid processing layer and provides recommendations for improvement
    - provides an answer to the question of how to solve the "black box" nature of AI models by providing users with interpretable insights into their motivation for their rankings and how suitable they are for a particular employment opportunity
    ```
    Explainability Toolkit:
    ├── SHAP:          Feature importance for SVM predictions
    ├── LIME:          Local explanations for individual resumes  
    ├── Attention Viz: Highlight BERT attention weights on key terms
    └── Skill Mapping: Visual skill-gap radar chart

    - Show matched keywords/skills highlighted in resume
    - Display skill-gap analysis: "You have 7/10 required skills for Data Scientist"
    - Provide actionable feedback: "Consider adding experience with TensorFlow"
    
> [!FriendlyUserInterface]
process of login 
guest login 
- change interface to guest mode that does not support save data or analysis
after analysis show the option to login or signup to save the data or analysis
signup 
- new user
- if the new user just signup when proceed to login menu immediately help them to insert their information in the login menu, allow them to press login button to login
login 
- existing user just login, refresh their profile and prompt welcome back [name]

analyze now 
- when user click this button it will analyze the resume and show the results
- during the time waiting for the analysis to complete, show a loading bar and a message that says "Analyzing your resume..."
- after the analysis is complete, show the results

[!afteranalysis]
guest login 
- after showing the result, prompt user to login or signup to save the data or analysis
existing user 
- after showing the result, save it immediately into history (show the uploaded resume and the result as well as the date and time of the analysis) and show the option to download the result
- can check the history of the analysis in the history page

[!Skillstab]
- show user the skills that are extracted from the resume
- show user the skills that are matched with the job requirements
- show user the skills that are not matched with the job requirements
- show user the skills that are recommended to improve

[!Gapstab]
- show user the gap between the user's skills and the job requirements
- show user the recommended skills to improve
- provide the reason for the gap and recommendations

[!Plantab]
- show user the plan for the user to improve their skills
- show user the recommended resources for the user to improve their skills
- provide the reason for the plan and recommendations

> [!evaluation]
1. classification performance
2. ranking quality
3. operational efficiency 
improving on the promise of a career-preparation support system with better fair play, speed, and accuracy
| Metric Category | Specific Metrics |
|-----------------|------------------|
| **Classification** | Accuracy, Precision, Recall, F1-score (macro/weighted), Confusion Matrix |
| **Ranking** | NDCG@k, MAP, MRR, Precision@k |
| **Efficiency** | Latency (P50, P95, P99), Throughput (resumes/sec), Memory usage |
| **Fairness** | Demographic parity, Equal opportunity, Bias audit by name/gender proxies |
| **User Satisfaction** | Feedback usefulness rating, Time to understand results |

> [!objectives]
1.	To develop an AI  resume screening web application that will be able to accurately collect and interpret the key points from the non-structured resumes using NLP.
2.	To build a recommendation system based on skill-gap analysis that classifies resumes into relevant job categories through semantic similarity and contextual representation.
3.	To implement a user-friendly screening interface that enables real-time interaction, visualization of rankings, and generation of candidate feedback
This project intends to conduct NLP operations on resumes in text format and then use ML models for assigning candidates to job categories based on their relevance. Besides, the system will be compatible with the different digital formats of resumes, and the feedback will be given through an interactive interface which will make it easy for anyone wanting to get career-ready to access the solution. 

> [!IMPORTANT]



### 🔴 GAP 8: Skill-Gap Analysis Undefined
**Issue**: Objective 2 mentions skill-gap analysis but no implementation details.

**Questions to Address**:
1. Where does the job requirements/skills database come from?
2. What skill taxonomy will be used? (O*NET, custom, extracted from job postings?)
3. How are skills matched? (Exact string? Semantic similarity? Synonym mapping?)

**Recommendations**:
```
Skill-Gap Pipeline:
1. Extract skills from resume using NER or keyword matching
2. Load job requirements from database/job description
3. Compare using:
   - Exact match for hard skills (Python, SQL)
   - Semantic similarity for soft skills (leadership ≈ management)
4. Calculate gap score and generate recommendations
```

---

### 🟠 Additional Implementation Challenges

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| Real-time BERT inference | 100-500ms latency | Model distillation, async processing, caching |
| Multi-format parsing failures | Broken text extraction | Robust fallbacks, manual review queue |
| Cold start for new job categories | Poor classification | Zero-shot classification, expandable taxonomy |
| Streamlit scalability | Not production-grade | Consider FastAPI + React for scale |
| Model drift over time | Accuracy degradation | Scheduled retraining, monitoring dashboard |

---

### ✅ Recommended Additions to Section 1

- [ ] **Data Pipeline Details**: Preprocessing steps, augmentation, train/val/test split ratios
- [ ] **Architecture Diagram**: Visual flowchart of Input → Processing → Output
- [ ] **Technology Stack Table**: Explicit libraries/frameworks for each layer
- [ ] **Performance Baselines**: Target latency (<500ms), accuracy (>85% F1), throughput
- [ ] **Fallback Mechanisms**: What happens when parsing fails or confidence is low?
- [ ] **Bias Mitigation Plan**: How to detect and address unfair predictions?

---

