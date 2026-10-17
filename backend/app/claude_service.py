from anthropic import Anthropic
from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .agent import get_product, history

def summarize_product(product_id):
    if not ANTHROPIC_API_KEY: raise RuntimeError("Claude is not configured. Add ANTHROPIC_API_KEY to backend/.env.")
    product = get_product(product_id)
    if not product: raise LookupError("Product not found.")
    records = history(product_id)
    if not records: raise RuntimeError("No price history is available yet.")
    prompt = ("Analyze this recorded product price history. Use only provided data, do not invent prices or forecasts, "
              "and mention that history may be limited. Give a concise summary and practical interpretation.\n\n"
              f"Product: {product['title']}\nURL: {product['url']}\nTarget: {product['target_price']}\n"
              f"Price records: {records[-30:]}")
    response = Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
        model=ANTHROPIC_MODEL, max_tokens=350, messages=[{"role":"user","content":prompt}])
    return "\n".join(block.text for block in response.content if getattr(block, "type", None) == "text")
