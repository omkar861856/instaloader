import requests
import os
from dotenv import load_dotenv

load_dotenv()

FILEFLOWS_URL = os.getenv("FILEFLOWS_URL")

class FileFlowsService:
    def __init__(self):
        self.base_url = FILEFLOWS_URL.rstrip('/') if FILEFLOWS_URL else None

    def _get(self, endpoint):
        if not self.base_url: return None
        try:
            response = requests.get(f"{self.base_url}/api/{endpoint}", timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"FileFlows GET Error ({endpoint}): {e}")
            return None

    def _post(self, endpoint, data=None):
        if not self.base_url: return False
        try:
            response = requests.post(f"{self.base_url}/api/{endpoint}", json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"FileFlows POST Error ({endpoint}): {e}")
            return False

    def _put(self, endpoint, data=None):
        if not self.base_url: return False
        try:
            response = requests.put(f"{self.base_url}/api/{endpoint}", json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"FileFlows PUT Error ({endpoint}): {e}")
            return False

    # Flow Management
    def get_flows(self):
        return self._get("flow/list-all") or []

    def export_flow(self, uid):
        return self._get(f"flow/export?uid={uid}")

    def get_flow(self, uid):
        return self._get(f"flow/{uid}")

    def get_flow_templates(self):
        return self._get("flow-template") or []

    # Library & Files
    def get_library_files(self, page=0, page_size=50):
        # The user provided list-all with page/pageSize
        return self._get(f"library-file/list-all?page={page}&pageSize={page_size}") or []

    def get_status(self):
        return self._get("library-file/status") or []

    def get_upcoming(self):
        return self._get("library-file/upcoming") or []

    def get_recently_finished(self):
        return self._get("library-file/recently-finished") or []

    # System & Nodes
    def get_executing(self):
        return self._get("worker") or []

    def get_nodes(self):
        return self._get("node") or []

    def get_system_info(self):
        return self._get("system/info") or {"error": "Unavailable"}

    # Actions
    def rescan_libraries(self):
        return self._put("library/rescan")

    def trigger_process(self, path, filename, library_uid):
        endpoint = f"library-file/process-file?filename={filename}&libraryUid={library_uid}"
        return self._post(endpoint, {"Path": path})

ff_service = FileFlowsService()
