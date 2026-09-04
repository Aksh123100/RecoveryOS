from dataclasses import dataclass,field
import time
@dataclass
class AuditLogger:
    events:list=field(default_factory=list)
    def record(self,event_type,**payload):
        self.events.append({"ts":time.time(),"event_type":event_type,**payload})
