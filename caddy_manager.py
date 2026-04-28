import os
import shutil
import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

def format_social_links(links: List[str]) -> str:
    if not any(links):
        return "لا يوجد"
    
    formatted = []
    
    fb_svg = '<svg style="width: 16px; height: 16px; vertical-align: middle; fill: #1877F2; margin-right: 5px;" viewBox="0 0 24 24"><path d="M22.675 0h-21.35c-.732 0-1.325.593-1.325 1.325v21.351c0 .731.593 1.324 1.325 1.324h11.495v-9.294h-3.128v-3.622h3.128v-2.671c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.312h3.587l-.467 3.622h-3.12v9.293h6.116c.73 0 1.323-.593 1.323-1.325v-21.35c0-.732-.593-1.325-1.325-1.325z"/></svg>'
    ig_svg = '<svg style="width: 16px; height: 16px; vertical-align: middle; fill: #E1306C; margin-right: 5px;" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>'
    tt_svg = '<svg style="width: 16px; height: 16px; vertical-align: middle; fill: #000000; margin-right: 5px;" viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>'

    for link in links:
        if not link:
            continue
        url = link if link.startswith('http') else 'https://' + link
        icon = ''
        if 'facebook.com' in url.lower() or 'fb.me' in url.lower():
            icon = fb_svg
        elif 'instagram.com' in url.lower() or 'ig.me' in url.lower():
            icon = ig_svg
        elif 'tiktok.com' in url.lower():
            icon = tt_svg
        
        formatted.append(f'<div style="margin-bottom: 5px;">{icon}<a href="{url}" target="_blank" style="color: var(--primary-color); text-decoration: none;" dir="ltr">{url}</a></div>')
    
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
        vhost_config = f"""{domain}, www.{domain} {{
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
