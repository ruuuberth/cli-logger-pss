from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from importlib.util import find_spec
from datetime import date, datetime

if find_spec("pssapi") is not None:
    from pssapi import PssApiClient  # type: ignore
else:
    PssApiClient = None  # type: ignore
from app.models.pss_models import ItemDesign, ShipDesign, CrewDesign

class PSSService:
    def __init__(self, db: Session):
        self.db = db
        self.client = PssApiClient() if PssApiClient is not None else None
    
    async def get_item_designs(self) -> List[Dict[str, Any]]:
        """Obtener y cachear diseños de items"""
        try:
            # Intentar obtener de la base de datos primero
            cached_items = self.db.query(ItemDesign).all()
            if cached_items:
                return [self._serialize_item_design(item) for item in cached_items]
            
            # Si no hay caché, obtener de la API
            if self.client is None:
                return []
            item_designs = await self.client.item_service.list_item_designs()
            
            # Guardar en base de datos
            for design in item_designs:
                db_item = ItemDesign(
                    item_design_id=design.item_design_id,
                    name=design.item_design_name,
                    description=getattr(design, 'description', ''),
                    rarity=getattr(design, 'rarity', ''),
                    item_type=getattr(design, 'item_type', ''),
                    stats=self._extract_stats(design),
                    raw_data=self._extract_raw_data(design)
                )
                self.db.add(db_item)
            
            self.db.commit()
            return [self._serialize_item_design(item) for item in self.db.query(ItemDesign).all()]
            
        except Exception as e:
            print(f"Error getting item designs: {e}")
            return []
    
    async def get_item_design(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Obtener un diseño de item específico"""
        try:
            # Buscar en base de datos
            cached_item = self.db.query(ItemDesign).filter(
                ItemDesign.item_design_id == item_id
            ).first()
            
            if cached_item:
                return self._serialize_item_design(cached_item)
            
            # Si no está en caché, obtener de API
            if self.client is None:
                return None
            item_design = await self.client.item_service.get_item_design(item_id)
            if item_design:
                db_item = ItemDesign(
                    item_design_id=item_design.item_design_id,
                    name=item_design.item_design_name,
                    description=getattr(item_design, 'description', ''),
                    rarity=getattr(item_design, 'rarity', ''),
                    item_type=getattr(item_design, 'item_type', ''),
                    stats=self._extract_stats(item_design),
                    raw_data=self._extract_raw_data(item_design)
                )
                self.db.add(db_item)
                self.db.commit()
                self.db.refresh(db_item)
                return self._serialize_item_design(db_item)
            
            return None
            
        except Exception as e:
            print(f"Error getting item design {item_id}: {e}")
            return None
    
    async def get_ship_designs(self) -> List[Dict[str, Any]]:
        """Obtener y cachear diseños de naves"""
        try:
            cached_ships = self.db.query(ShipDesign).all()
            if cached_ships:
                return [self._serialize_ship_design(ship) for ship in cached_ships]
            
            if self.client is None:
                return []
            ship_designs = await self.client.ship_service.list_ship_designs()
            
            for design in ship_designs:
                db_ship = ShipDesign(
                    ship_design_id=design.ship_design_id,
                    name=design.ship_design_name,
                    description=getattr(design, 'description', ''),
                    class_type=getattr(design, 'class_type', ''),
                    stats=self._extract_stats(design),
                    raw_data=self._extract_raw_data(design)
                )
                self.db.add(db_ship)
            
            self.db.commit()
            return [self._serialize_ship_design(ship) for ship in self.db.query(ShipDesign).all()]
            
        except Exception as e:
            print(f"Error getting ship designs: {e}")
            return []
    
    async def get_ship_design(self, ship_id: int) -> Optional[Dict[str, Any]]:
        """Obtener un diseño de nave específico"""
        try:
            cached_ship = self.db.query(ShipDesign).filter(
                ShipDesign.ship_design_id == ship_id
            ).first()
            
            if cached_ship:
                return self._serialize_ship_design(cached_ship)
            
            if self.client is None:
                return None
            ship_design = await self.client.ship_service.get_ship_design(ship_id)
            if ship_design:
                db_ship = ShipDesign(
                    ship_design_id=ship_design.ship_design_id,
                    name=ship_design.ship_design_name,
                    description=getattr(ship_design, 'description', ''),
                    class_type=getattr(ship_design, 'class_type', ''),
                    stats=self._extract_stats(ship_design),
                    raw_data=self._extract_raw_data(ship_design)
                )
                self.db.add(db_ship)
                self.db.commit()
                self.db.refresh(db_ship)
                return self._serialize_ship_design(db_ship)
            
            return None
            
        except Exception as e:
            print(f"Error getting ship design {ship_id}: {e}")
            return None
    
    async def get_crew_designs(self) -> List[Dict[str, Any]]:
        """Obtener y cachear diseños de tripulación"""
        try:
            cached_crews = self.db.query(CrewDesign).all()
            if cached_crews:
                return [self._serialize_crew_design(crew) for crew in cached_crews]
            
            if self.client is None:
                return []
            crew_designs = await self.client.crew_service.list_crew_designs()
            
            for design in crew_designs:
                db_crew = CrewDesign(
                    crew_design_id=design.crew_design_id,
                    name=design.crew_design_name,
                    description=getattr(design, 'description', ''),
                    race=getattr(design, 'race', ''),
                    role=getattr(design, 'role', ''),
                    stats=self._extract_stats(design),
                    raw_data=self._extract_raw_data(design)
                )
                self.db.add(db_crew)
            
            self.db.commit()
            return [self._serialize_crew_design(crew) for crew in self.db.query(CrewDesign).all()]
            
        except Exception as e:
            print(f"Error getting crew designs: {e}")
            return []
    
    async def get_crew_design(self, crew_id: int) -> Optional[Dict[str, Any]]:
        """Obtener un diseño de tripulación específico"""
        try:
            cached_crew = self.db.query(CrewDesign).filter(
                CrewDesign.crew_design_id == crew_id
            ).first()
            
            if cached_crew:
                return self._serialize_crew_design(cached_crew)
            
            if self.client is None:
                return None
            crew_design = await self.client.crew_service.get_crew_design(crew_id)
            if crew_design:
                db_crew = CrewDesign(
                    crew_design_id=crew_design.crew_design_id,
                    name=crew_design.crew_design_name,
                    description=getattr(crew_design, 'description', ''),
                    race=getattr(crew_design, 'race', ''),
                    role=getattr(crew_design, 'role', ''),
                    stats=self._extract_stats(crew_design),
                    raw_data=self._extract_raw_data(crew_design)
                )
                self.db.add(db_crew)
                self.db.commit()
                self.db.refresh(db_crew)
                return self._serialize_crew_design(db_crew)
            
            return None
            
        except Exception as e:
            print(f"Error getting crew design {crew_id}: {e}")
            return None
    
    def _serialize_item_design(self, item: ItemDesign) -> Dict[str, Any]:
        return {
            "id": item.item_design_id,
            "name": item.name,
            "description": item.description,
            "rarity": item.rarity,
            "item_type": item.item_type,
            "stats": item.stats,
            "created_at": item.created_at.isoformat() if item.created_at else None
        }
    
    def _serialize_ship_design(self, ship: ShipDesign) -> Dict[str, Any]:
        return {
            "id": ship.ship_design_id,
            "name": ship.name,
            "description": ship.description,
            "class_type": ship.class_type,
            "stats": ship.stats,
            "created_at": ship.created_at.isoformat() if ship.created_at else None
        }
    
    def _serialize_crew_design(self, crew: CrewDesign) -> Dict[str, Any]:
        return {
            "id": crew.crew_design_id,
            "name": crew.name,
            "description": crew.description,
            "race": crew.race,
            "role": crew.role,
            "stats": crew.stats,
            "created_at": crew.created_at.isoformat() if crew.created_at else None
        }
    
    def _extract_stats(self, obj) -> Dict[str, Any]:
        """Extraer estadísticas relevantes del objeto"""
        stats = {}
        stat_attributes = ['attack', 'defense', 'health', 'speed', 'critical', 'dodge']
        
        for attr in stat_attributes:
            if hasattr(obj, attr):
                stats[attr] = getattr(obj, attr)
        
        return stats

    def _extract_raw_data(self, obj: Any) -> Dict[str, Any]:
        """Convertir objetos del cliente PSS a una estructura serializable para JSON."""
        # pssapi puede exponer __dict__ como método en vez de atributo.
        obj_dict = getattr(obj, "__dict__", None)
        if callable(obj_dict):
            try:
                return self._to_jsonable(obj_dict())
            except Exception:
                pass
        elif isinstance(obj_dict, dict):
            return self._to_jsonable(obj_dict)

        try:
            return self._to_jsonable(vars(obj))
        except TypeError:
            return self._to_jsonable(obj)

    def _to_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(k): self._to_jsonable(v)
                for k, v in value.items()
                if not callable(v)
            }

        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(v) for v in value]

        if callable(value):
            return str(value)

        nested_dict = getattr(value, "__dict__", None)
        if callable(nested_dict):
            try:
                return self._to_jsonable(nested_dict())
            except Exception:
                return str(value)
        if isinstance(nested_dict, dict):
            return self._to_jsonable(nested_dict)

        return str(value)
