import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    TRANSACTIONS_SHEET: str = "transactions"
    CATEGORIES_SHEET: str = "categories"
    FIXED_EXPENSES_SHEET: str = "fixed_expenses"
    BUDGETS_SHEET: str = "budgets"


settings = Settings()
