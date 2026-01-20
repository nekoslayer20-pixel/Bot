```python
# utils/api.py
import os
import aiohttp
import asyncio
import hashlib
import secrets
from typing import Optional, Dict, Any, List

PTERO_APP_API = os.environ.get("PTERO_APP_API")  # Application API key (Bearer)
PTERO_CLIENT_API = os.environ.get("PTERO_CLIENT_API")  # (optional) Daemon API key if needed
PTERO_PANEL_URL = os.environ.get("PTERO_PANEL_URL", "https://panel.example.com").rstrip("/")

if not PTERO_APP_API:
    raise RuntimeError("PTERO_APP_API environment variable is required")

class PteroError(Exception):
    pass

class PteroAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = PTERO_PANEL_URL
        self.headers = {
            "Authorization": f"Bearer {PTERO_APP_API}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    @staticmethod
    def generate_password(length: int = 16) -> str:
        return secrets.token_urlsafe(length)[:length]

    # --- Node & Egg helpers ---
    async def get_node(self, node_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/api/application/nodes/{node_id}"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                resp = await r.json()
                return resp.get("attributes", resp)
            raise PteroError(f"Node {node_id} not found (status {r.status})")

    async def get_egg(self, egg_id: int) -> Dict[str, Any]:
        # The Pterodactyl API typically exposes eggs via: /api/application/nests/{nest_id}/eggs/{egg_id}
        # Many panels also allow /api/application/eggs/{egg_id}
        url = f"{self.base_url}/api/application/nests"
        # Try a direct eggs endpoint first
        try:
            url_direct = f"{self.base_url}/api/application/eggs/{egg_id}"
            async with self.session.get(url_direct, headers=self.headers) as r:
                if r.status == 200:
                    resp = await r.json()
                    return resp.get("attributes", resp)
        except Exception:
            pass
        # Fallback: list nests and search eggs
        async with self.session.get(url, headers=self.headers) as r:
            if r.status != 200:
                raise PteroError("Unable to fetch nests to validate egg")
            nests = await r.json()
            for n in nests.get("data", []):
                nest_id = n.get("attributes", {}).get("id")
                if not nest_id:
                    continue
                eggs_url = f"{self.base_url}/api/application/nests/{nest_id}/eggs"
                async with self.session.get(eggs_url, headers=self.headers) as er:
                    if er.status != 200:
                        continue
                    eggs = await er.json()
                    for egg in eggs.get("data", []):
                        if egg.get("attributes", {}).get("id") == egg_id or egg.get("id") == egg_id:
                            return egg.get("attributes", egg)
        raise PteroError(f"Egg {egg_id} not found")

    # --- User helpers ---
    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/application/users?filter[email]={email}"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status != 200:
                # Fallback to listing and matching
                users = await self.list_users()
                for u in users.get("data", []):
                    a = u.get("attributes", {})
                    if a.get("email") == email:
                        return a
                return None
            data = await r.json()
            for u in data.get("data", []):
                return u.get("attributes", u)
        return None

    async def create_user(self, username: str, email: str, first_name: str, last_name: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/application/users"
        payload = {
            "username": username[:191],
            "email": email,
            "first_name": first_name[:191],
            "last_name": last_name[:191],
            "password": password
        }
        async with self.session.post(url, json=payload, headers=self.headers) as r:
            if r.status in (200, 201):
                data = await r.json()
                return data.get("attributes", data)
            else:
                text = await r.text()
                raise PteroError(f"Create user failed: status {r.status}: {text}")

    async def list_users(self, page: int = 1) -> Dict[str, Any]:
        url = f"{self.base_url}/api/application/users?page={page}"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                return await r.json()
            raise PteroError(f"List users failed (status {r.status})")

    async def delete_user(self, user_id: int):
        url = f"{self.base_url}/api/application/users/{user_id}"
        async with self.session.delete(url, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Delete user failed: status {r.status}: {text}")

    async def change_user_password(self, user_id: int, password: str):
        url = f"{self.base_url}/api/application/users/{user_id}/reset-password"
        payload = {"password": password, "password_confirmation": password}
        async with self.session.post(url, json=payload, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Change password failed: status {r.status}: {text}")

    # --- Server helpers ---
    async def create_server(self, name: str, user_id: int, egg_id: int, node_id: int, memory: int, cpu: int, disk: int, version: str) -> Dict[str, Any]:
        """
        Create a server. This tries to craft a typical payload compatible with Pterodactyl Application API.
        The API may vary; administrators should adapt fields like allocation if necessary.
        """
        url = f"{self.base_url}/api/application/servers"
        payload = {
            "name": name[:191],
            "user": int(user_id),
            "egg": int(egg_id),
            "docker_image": version,
            "startup": None,
            "environment": {},
            "limits": {
                "memory": int(memory),
                "swap": 0,
                "disk": int(disk),
                "io": 500,
                "cpu": int(cpu)
            },
            "feature_limits": {},
            "node": int(node_id),
            "allocation": {}
        }
        # Note: allocation might be required by some panels; leaving allocation empty may cause failure.
        async with self.session.post(url, json=payload, headers=self.headers) as r:
            if r.status in (200, 201):
                data = await r.json()
                return data.get("attributes", data)
            text = await r.text()
            raise PteroError(f"Create server failed: status {r.status}: {text}")

    async def delete_server(self, server_id: str):
        url = f"{self.base_url}/api/application/servers/{server_id}"
        async with self.session.delete(url, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Delete server failed: status {r.status}: {text}")

    async def suspend_server(self, server_id: str):
        url = f"{self.base_url}/api/application/servers/{server_id}/suspend"
        async with self.session.post(url, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Suspend failed: status {r.status}: {text}")

    async def unsuspend_server(self, server_id: str):
        url = f"{self.base_url}/api/application/servers/{server_id}/unsuspend"
        async with self.session.post(url, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Unsuspend failed: status {r.status}: {text}")

    async def get_server(self, server_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/application/servers/{server_id}"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                return await r.json()
            text = await r.text()
            raise PteroError(f"Get server failed: status {r.status}: {text}")

    async def list_servers(self, page: int = 1) -> Dict[str, Any]:
        url = f"{self.base_url}/api/application/servers?page={page}"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                return await r.json()
            raise PteroError(f"List servers failed: status {r.status}")

    async def search_servers(self, query: str) -> List[Dict[str, Any]]:
        # Pterodactyl does not provide a universal search endpoint by default. This tries to do a basic scan.
        all_pages = await self.list_servers(page=1)
        results = []
        for item in all_pages.get("data", []):
            a = item.get("attributes", {})
            if query.lower() in a.get("name", "").lower() or query.lower() in a.get("identifier", "").lower():
                results.append(a)
        return results

    async def set_server_resources(self, server_id: str, memory: int, cpu: int, disk: int):
        url = f"{self.base_url}/api/application/servers/{server_id}/build"
        payload = {
            "memory": int(memory),
            "swap": 0,
            "disk": int(disk),
            "io": 500,
            "cpu": int(cpu)
        }
        async with self.session.patch(url, json=payload, headers=self.headers) as r:
            if r.status in (200, 204):
                return True
            text = await r.text()
            raise PteroError(f"Set resources failed: status {r.status}: {text}")

    # --- Panel endpoints ---
    async def list_nodes(self):
        url = f"{self.base_url}/api/application/nodes"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                resp = await r.json()
                return [d.get("attributes", d) for d in resp.get("data", [])]
            raise PteroError("Failed to list nodes")

    async def list_eggs(self):
        url = f"{self.base_url}/api/application/nests"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status != 200:
                raise PteroError("Failed to fetch nests/eggs")
            resp = await r.json()
            eggs = []
            for n in resp.get("data", []):
                nid = n.get("attributes", {}).get("id")
                async with self.session.get(f"{self.base_url}/api/application/nests/{nid}/eggs", headers=self.headers) as er:
                    if er.status != 200:
                        continue
                    eresp = await er.json()
                    for e in eresp.get("data", []):
                        eggs.append(e.get("attributes", e))
            return eggs

    async def panel_status(self) -> str:
        # Simple check: GET panel root or API health
        async with self.session.get(f"{self.base_url}/api/application") as r:
            if r.status == 200:
                return "OK"
            return f"Unclear (status {r.status})"

    async def list_backups(self, server_id: str):
        url = f"{self.base_url}/api/application/servers/{server_id}/backups"
        async with self.session.get(url, headers=self.headers) as r:
            if r.status == 200:
                resp = await r.json()
                return resp.get("data", [])
            raise PteroError(f"List backups failed: status {r.status}")

    # --- Simple user search ---
    async def search_users(self, query: str):
        users = await self.list_users(page=1)
        matches = []
        for u in users.get("data", []):
            a = u.get("attributes", {})
            if query.lower() in a.get("username", "").lower() or query.lower() in a.get("email", "").lower():
                matches.append(a)
        return matches
```
