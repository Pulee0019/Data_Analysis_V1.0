from infrastructure.logger import log_message

class AnalysisResultsManager:
    """Manage analysis results for all animals"""
    def __init__(self):
        self.last_analysis_type = None  # Track last analysis type
    
    def set_last_analysis(self, analysis_type):
        """Set the last performed analysis type"""
        self.last_analysis_type = analysis_type
        log_message(f"Last analysis type set to: {analysis_type}", "INFO")
    
    def get_last_analysis(self):
        """Get the last performed analysis type"""
        return self.last_analysis_type
