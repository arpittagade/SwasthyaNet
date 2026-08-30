from __future__ import annotations

from datetime import date, timedelta
from random import Random

from . import db_manager

MEDICINES = [
    {"id": "paracetamol", "name": "Paracetamol 500mg", "unit": "tablets", "category": "analgesic"},
    {"id": "ors", "name": "ORS Sachets", "unit": "sachets", "category": "essential"},
    {"id": "amoxicillin", "name": "Amoxicillin 500mg", "unit": "capsules", "category": "antibiotic"},
    {"id": "azithromycin", "name": "Azithromycin 250mg", "unit": "tablets", "category": "antibiotic"},
    {"id": "iron", "name": "Iron Folic Acid", "unit": "tablets", "category": "maternal"},
    {"id": "salbutamol", "name": "Salbutamol Inhaler", "unit": "inhalers", "category": "respiratory"},
    {"id": "insulin", "name": "Human Insulin", "unit": "vials", "category": "chronic"},
    {"id": "artesunate", "name": "Artesunate", "unit": "vials", "category": "critical"},
    {"id": "ivfluids", "name": "IV Fluids", "unit": "bags", "category": "essential"},
    {"id": "oxytocin", "name": "Oxytocin", "unit": "vials", "category": "maternal"},
    {"id": "zinc", "name": "Zinc Dispersible", "unit": "tablets", "category": "paediatric"},
    {"id": "gloves", "name": "Examination Gloves", "unit": "boxes", "category": "consumable"},
]

PHCS = [
    {"id": "phc-rajapur", "name": "Rajapur PHC", "district": "Nashik", "lat": 20.02, "lon": 73.79, "beds": 30},
    {"id": "phc-sinnar", "name": "Sinnar PHC", "district": "Nashik", "lat": 19.85, "lon": 73.99, "beds": 24},
    {"id": "phc-khed", "name": "Khed Rural Hospital", "district": "Pune", "lat": 18.84, "lon": 73.89, "beds": 36},
    {"id": "phc-bhor", "name": "Bhor PHC", "district": "Pune", "lat": 18.15, "lon": 73.84, "beds": 20},
    {"id": "phc-wai", "name": "Wai PHC", "district": "Satara", "lat": 17.95, "lon": 73.89, "beds": 28},
    {"id": "phc-karad", "name": "Karad PHC", "district": "Satara", "lat": 17.29, "lon": 74.18, "beds": 32},
]

class SimulationState:
    def __init__(self, seed: int = 42):
        self.rng = Random(seed)
        db_manager.init_db()
        restored = db_manager.load_state()
        if restored is not None:
            day_str, tick, phcs = restored
            self.day = date.fromisoformat(day_str)
            self.tick = tick
            self.phcs = phcs
            return
        self.day = date.today() - timedelta(days=29)
        self.tick = 0
        self.phcs = []
        for p_idx, phc in enumerate(PHCS):
            inventory = []
            for m_idx, med in enumerate(MEDICINES):
                daily = 4 + ((p_idx * 3 + m_idx) % 9)
                capacity = daily * (16 + ((m_idx + p_idx) % 12))
                quantity = capacity
                if phc["id"] == "phc-rajapur" and med["id"] == "paracetamol": quantity = 22
                if phc["id"] == "phc-sinnar" and med["id"] == "paracetamol": quantity = 210
                if phc["id"] == "phc-khed" and med["id"] == "ivfluids": quantity = 18
                inventory.append({"medicine_id": med["id"], "quantity": quantity, "threshold": daily * 7, "daily": daily, "history": []})
            phc_state = {**phc, "inventory": inventory, "occupied": int(phc["beds"] * (0.52 + (p_idx % 3) * 0.08)), "attendance": round(89 - p_idx * 2.2, 1), "history": []}
            for _ in range(30): self._record_day(phc_state, historical=True)
            self.phcs.append(phc_state)
        db_manager.save_state(self.day.isoformat(), self.tick, self.phcs)

    def _record_day(self, phc, historical=False):
        for item in phc["inventory"]:
            noise = self.rng.choice([-1, 0, 0, 1, 2])
            use = max(1, item["daily"] + noise)
            if not historical: item["quantity"] = max(0, item["quantity"] - use)
            item["history"].append(use)
            item["history"] = item["history"][-30:]
        change = self.rng.choice([-2, -1, 0, 0, 1, 2])
        phc["occupied"] = max(0, min(phc["beds"], phc["occupied"] + change))
        phc["attendance"] = round(max(60, min(100, phc["attendance"] + self.rng.uniform(-2.2, 1.6))), 1)
        phc["history"].append({"date": self.day.isoformat(), "occupied": phc["occupied"], "attendance": phc["attendance"]})
        phc["history"] = phc["history"][-30:]

    def advance(self):
        self.tick += 1
        self.day += timedelta(days=1)
        for phc in self.phcs: self._record_day(phc)
        db_manager.save_state(self.day.isoformat(), self.tick, self.phcs)
        return self.snapshot()

    def snapshot(self):
        return {"day": self.day.isoformat(), "tick": self.tick, "phcs": self.phcs, "medicines": MEDICINES}

STATE = SimulationState()
