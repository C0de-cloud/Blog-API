import re
from slugify import slugify


def generate_slug(text: str) -> str:
    return slugify(text)


def is_valid_slug(slug: str) -> bool:
    return bool(re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug))


def get_summary_from_content(content: str, max_length: int = 200) -> str:
    if len(content) <= max_length:
        return content
    
    summary = content[:max_length]
    last_space = summary.rfind(' ')
    
    if last_space != -1:
        summary = summary[:last_space]
    
    return summary.rstrip() + "..." 