from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus

class Settings(BaseSettings):
    app_name: str = "AI Social Media Content Assistant"
    jwt_secret_key: str
    jwt_expire_minutes: int = 1440
    opspilot_db_host: str = "127.0.0.1"
    opspilot_db_port: int = 3306
    opspilot_db_name: str = "ai_social_assistant"
    opspilot_db_user: str = "root"
    opspilot_db_password: str
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: int = 180
    social_token_encryption_key: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://127.0.0.1:8000/oauth/facebook/callback"
    meta_instagram_redirect_uri: str = "http://127.0.0.1:8000/oauth/instagram/callback"
    meta_graph_version: str = "v23.0"
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://127.0.0.1:8000/oauth/linkedin/callback"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    @property
    def database_url(self):
        return (f"mysql+pymysql://{quote_plus(self.opspilot_db_user)}:{quote_plus(self.opspilot_db_password)}"
                f"@{self.opspilot_db_host}:{self.opspilot_db_port}/{quote_plus(self.opspilot_db_name)}?charset=utf8mb4")
settings = Settings()
