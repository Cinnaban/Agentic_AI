

class Config:

    # ==========================================
    # Ollama / Models
    # ==========================================
    QWEN_MODEL = "qwen3:30b"
    GEMMA_MODEL = "gemma4:12b"
    HERMES_MODEL = "hermes3:latest"
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_GENERATE_ENDPOINT = (
        f"{OLLAMA_HOST}/api/generate"
    )

    # ==========================================
    # Agent Model Assignments
    # ==========================================

    ORCHESTRATOR_MODEL = HERMES_MODEL

    COMPANY_DETECTION_MODEL = HERMES_MODEL

    RESEARCH_MODEL = GEMMA_MODEL
    
    RESEARCH_ASSIGNMENT_MODEL = HERMES_MODEL

    SENTIMENT_MODEL = HERMES_MODEL

    RISK_MODEL = HERMES_MODEL

    SIGNAL_RECONCILIATION_MODEL = HERMES_MODEL

    QUALITY_MODEL = HERMES_MODEL

    GENERAL_RESPONSE_MODEL = HERMES_MODEL
    # ==========================================
    # Gaming PC Compute Worker
    # ==========================================

    GAMING_PC_WORKER_NAME = "gaming_pc"

    GAMING_PC_HOST = "192.168.50.1"

    GAMING_PC_PORT = 8001

    GAMING_PC_BASE_URL = (
        f"http://{GAMING_PC_HOST}:{GAMING_PC_PORT}"
    )

    GAMING_PC_HEALTH_URL = (
        f"{GAMING_PC_BASE_URL}/health"
    )

    GAMING_PC_COMPUTE_URL = (
        f"{GAMING_PC_BASE_URL}/compute"
    )

    GAMING_PC_TIMEOUT = 300
    # ==========================================
    # Agent Settings
    # ==========================================

    AGENT_MODE = "research"
    QWEN_ENABLE_THINKING = False
    
    RESEARCH_NUM_PREDICT = 2048
    RESEARCH_NUM_CTX = 16384
    
    MAX_PORTFOLIO_ROWS = 250
    MAX_PROMPT_HOLDINGS = 50
    MAX_RESPONSE_LENGTH = 5000
    MAX_TICKERS_PER_QUERY = 10
    MAX_LIVE_LOOKUPS = 20
    MAX_NEWS_HEADLINES = 7
    MARKET_NEWS_LIMIT = 20

    ENABLE_HERMES = True
    ENABLE_TOOL_USE = True
    ENABLE_REASONING = True
    ENABLE_LIVE_DATA = True
    ENABLE_SHEET_DATA = True
    ENABLE_NEWS = True 
    ENABLE_MARKET_RESEARCH = True
    ENABLE_BETA_ANALYSIS = True
    ENABLE_SENTIMENT_ANALYSIS = True
    ENABLE_MARKET_PREDICTIONS = True

    PREDICTION_HORIZON_DAYS = 7
    # ==========================================
    # Model Settings
    # ==========================================

    MODEL_TEMPERATURE = 0.3
    MODEL_CONTEXT = 8192
    MODEL_NUM_PREDICT = 1024

    # ==========================================
    #  Memory Recall
    # ==========================================
    MEMORY_FILE = "./data/memory.json"

    CONVERSATION_HISTORY_LIMIT = 30

    ENABLE_MEMORY = True

    # ==========================================
    # Shared Storage
    # ==========================================

    SHARED_STORAGE_DIRECTORY = (
    "/Volumes/AIProjects/hermes"
)

    JOB_INCOMING_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/incoming"
    )

    JOB_PROCESSING_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/processing"
    )

    JOB_COMPLETED_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/completed"
    )

    JOB_FAILED_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/failed"
    )

    JOB_ARCHIVE_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/archive"
    )

    JOB_TEMP_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/temp"
    )
    # ==========================================
    # Storage Retention
    # ==========================================

    COMPLETED_JOB_RETENTION_DAYS = 30
    FAILED_JOB_RETENTION_DAYS = 30
    ARCHIVE_RETENTION_DAYS = 180
    TEMP_RETENTION_DAYS = 7

    ENABLE_STORAGE_CLEANUP = True
    # ==========================================
    # Linux Paths
    # ==========================================

    ENVIRONMENT = "production"
    DEBUG = False 

    DATA_DIRECTORY = "./data"
    RESULTS_DIRECTORY = "./results"
    
    # ==========================================
    # Logging
    # ==========================================

    LOG_DIRECTORY = (
        f"{SHARED_STORAGE_DIRECTORY}/completed"
    )
    # ==========================================
    #  Agent Personas
    # ==========================================

    AGENT_NAME = "Stock/ETF Research Agent"

    SYSTEM_PROMPT = """
    You are the Senior ETF and Stock Research Analyst.

    Your responsibilities:

    - Analyze portfolio holdings.
    - Compare ETFs and stocks.
    - Evaluate dividend quality and sustainability.
    - Evaluate expense ratios and costs.
    - Identify concentration risks.
    - Highlight notable valuation metrics.

    Rules:

    - Use portfolio data whenever available.
    - Use live market data when supplied.
    - Distinguish facts from opinion.
    - Never fabricate financial data.
    - Be concise and useful.
    - Format responses for Discord.
    """

