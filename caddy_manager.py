import os
import shutil
import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

def format_social_links(links: List[str]) -> str:
    if not links:
        return "لا يوجد"
    
    formatted = []
    for link in links:
        if not link:
            continue
        url = link if link.startswith('http') else 'https://' + link
        formatted.append(f'<div style="margin-bottom: 5px;"><a href="{url}" target="_blank" style="color: var(--primary-color); text-decoration: none;" dir="ltr">{url}</a></div>')
    
    return "\n".join(formatted)

def reload_caddy():
    try:
        with open('/etc/caddy/Caddyfile', 'rb') as f:
            caddyfile_content = f.read()
        
        response = requests.post(
            'http://caddy:2019/load',
            headers={'Content-Type': 'text/caddyfile'},
            data=caddyfile_content,
            timeout=10
        )
        if response.status_code != 200:
            logger.error(f"Failed to reload Caddy: {response.text}")
            return False
        logger.info("Caddy reloaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error reloading Caddy: {e}")
        return False

def setup_domain_files(
    domain: str, 
    store_name: str, 
    phone: str, 
    address: str, 
    email: str, 
    social_media: List[str]
) -> bool:
    if not domain or '..' in domain or '/' in domain:
        logger.error("Invalid domain name")
        return False

    hosting_dir = f"/app/hosting/{domain}"
    vhosts_dir = "/app/vhosts"
    
    is_subdomain = domain.endswith(".tejara.ps")
    caddyfile_path = f"{vhosts_dir}/{domain}_{'subdomain' if is_subdomain else 'custom'}.caddyfile"

    os.makedirs(vhosts_dir, exist_ok=True)
    os.makedirs(hosting_dir, exist_ok=True)

    # Process index.html
    try:
        with open("/app/htmls/index.html", "r", encoding="utf-8") as f:
            index_content = f.read()

        index_content = index_content.replace("[STORE_NAME]", store_name or "")
        index_content = index_content.replace("[PHONE]", phone or "")
        index_content = index_content.replace("[EMAIL]", email or "")
        index_content = index_content.replace("[ADDRESS]", address or "")
        index_content = index_content.replace("[LINK]", format_social_links(social_media))

        with open(f"{hosting_dir}/index.html", "w", encoding="utf-8") as f:
            f.write(index_content)
    except Exception as e:
        logger.error(f"Error processing index.html: {e}")
        return False

    # Copy policies.html
    try:
        if os.path.exists("/app/htmls/policies.html"):
            shutil.copy2("/app/htmls/policies.html", f"{hosting_dir}/policies.html")
    except Exception as e:
        logger.error(f"Error copying policies.html: {e}")
        # Not a fatal error if policies.html doesn't exist, but log it

    # Generate Caddyfile block
    if is_subdomain:
        safe_domain = domain.replace('.', '_')
        vhost_config = f"""@{safe_domain} host {domain}
handle @{safe_domain} {{
    root * /usr/share/caddy/hosting/{domain}
    file_server
}}
"""
    else:
        vhost_config = f"""{domain} {{
    root * /usr/share/caddy/hosting/{domain}
    file_server
}}
"""
    try:
        with open(caddyfile_path, "w", encoding="utf-8") as f:
            f.write(vhost_config)
    except Exception as e:
        logger.error(f"Error writing caddyfile block: {e}")
        return False

    return True

def remove_domain_files(domain: str) -> bool:
    if not domain or '..' in domain or '/' in domain:
        logger.error("Invalid domain name")
        return False

    hosting_dir = f"/app/hosting/{domain}"
    vhosts_dir = "/app/vhosts"
    
    is_subdomain = domain.endswith(".tejara.ps")
    caddyfile_path = f"{vhosts_dir}/{domain}_{'subdomain' if is_subdomain else 'custom'}.caddyfile"

    try:
        if os.path.exists(hosting_dir):
            shutil.rmtree(hosting_dir)
            
        if os.path.exists(caddyfile_path):
            os.remove(caddyfile_path)
            
        return True
    except Exception as e:
        logger.error(f"Error removing files for {domain}: {e}")
        return False
