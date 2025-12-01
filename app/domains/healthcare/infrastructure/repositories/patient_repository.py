"""
Patient Repository Implementation

SQLAlchemy implementation of IPatientRepository.
"""

import logging
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.healthcare.application.ports.patient_repository import IPatientRepository
from app.domains.healthcare.domain.entities.patient import Patient, Insurance, EmergencyContact
from app.domains.healthcare.domain.value_objects.appointment_status import PatientStatus, VitalSigns
from app.domains.healthcare.infrastructure.persistence.sqlalchemy.models import PatientModel
from app.core.domain import Email, PhoneNumber, Address

logger = logging.getLogger(__name__)


class SQLAlchemyPatientRepository(IPatientRepository):
    """
    SQLAlchemy implementation of patient repository.

    Handles all patient data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def find_by_id(self, patient_id: int) -> Patient | None:
        """Find patient by ID."""
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == patient_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_national_id(self, national_id: str) -> Patient | None:
        """Find patient by national ID."""
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.national_id == national_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_medical_record_number(self, mrn: str) -> Patient | None:
        """Find patient by medical record number."""
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.medical_record_number == mrn)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_phone(self, phone: str) -> Patient | None:
        """Find patient by phone number."""
        # Normalize phone for search
        normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
        result = await self.session.execute(
            select(PatientModel).where(
                func.replace(func.replace(PatientModel.phone, "-", ""), " ", "").like(f"%{normalized}%")
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def search(self, query: str, limit: int = 10) -> list[Patient]:
        """Search patients by name."""
        search_term = f"%{query}%"
        result = await self.session.execute(
            select(PatientModel)
            .where(
                or_(
                    PatientModel.first_name.ilike(search_term),
                    PatientModel.last_name.ilike(search_term),
                    PatientModel.national_id.ilike(search_term),
                    PatientModel.medical_record_number.ilike(search_term),
                )
            )
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def filter_by_status(self, status: PatientStatus, limit: int = 100) -> list[Patient]:
        """Filter patients by status."""
        result = await self.session.execute(
            select(PatientModel)
            .where(PatientModel.status == status)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_by_date_of_birth(self, start_date: date, end_date: date) -> list[Patient]:
        """Find patients born within date range."""
        result = await self.session.execute(
            select(PatientModel).where(
                PatientModel.date_of_birth.between(start_date, end_date)
            )
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def save(self, patient: Patient) -> Patient:
        """Save or update patient."""
        if patient.id:
            # Update existing
            result = await self.session.execute(
                select(PatientModel).where(PatientModel.id == patient.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_model(model, patient)
            else:
                model = self._to_model(patient)
                self.session.add(model)
        else:
            # Create new
            model = self._to_model(patient)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        return self._to_entity(model)

    async def delete(self, patient_id: int) -> bool:
        """Delete patient."""
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == patient_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def exists(self, patient_id: int) -> bool:
        """Check if patient exists."""
        result = await self.session.execute(
            select(func.count()).where(PatientModel.id == patient_id)
        )
        return result.scalar_one() > 0

    async def count(self) -> int:
        """Get total patient count."""
        result = await self.session.execute(select(func.count()).select_from(PatientModel))
        return result.scalar_one()

    async def count_by_status(self, status: PatientStatus) -> int:
        """Count patients by status."""
        result = await self.session.execute(
            select(func.count()).where(PatientModel.status == status)
        )
        return result.scalar_one()

    # Mapping methods

    def _to_entity(self, model: PatientModel) -> Patient:
        """Convert model to entity."""
        # Note: SQLAlchemy Column() syntax - Pyright sees Column objects at class level.
        # Build optional value objects
        email = Email(model.email) if model.email else None  # type: ignore[arg-type]
        phone = PhoneNumber(model.phone) if model.phone else None  # type: ignore[arg-type]

        address = None
        if model.address_street:
            address = Address(
                street=model.address_street,  # type: ignore[arg-type]
                city=model.address_city or "",  # type: ignore[arg-type]
                state=model.address_state or "",  # type: ignore[arg-type]
                postal_code=model.address_postal_code or "",  # type: ignore[arg-type]
                country=model.address_country or "Argentina",  # type: ignore[arg-type]
            )

        emergency_contact = None
        if model.emergency_contact_name:
            emergency_contact = EmergencyContact(
                name=model.emergency_contact_name,  # type: ignore[arg-type]
                relationship=model.emergency_contact_relationship or "",  # type: ignore[arg-type]
                phone=model.emergency_contact_phone or "",  # type: ignore[arg-type]
                email=model.emergency_contact_email,  # type: ignore[arg-type]
            )

        insurance = None
        if model.insurance_provider:
            insurance = Insurance(
                provider=model.insurance_provider,  # type: ignore[arg-type]
                policy_number=model.insurance_policy_number or "",  # type: ignore[arg-type]
                group_number=model.insurance_group_number,  # type: ignore[arg-type]
                valid_until=model.insurance_valid_until,  # type: ignore[arg-type]
            )

        last_vitals = None
        if model.last_vitals:
            try:
                last_vitals = VitalSigns(**model.last_vitals)  # type: ignore[arg-type]
            except Exception:
                pass

        patient = Patient(
            id=model.id,  # type: ignore[arg-type]
            first_name=model.first_name,  # type: ignore[arg-type]
            last_name=model.last_name,  # type: ignore[arg-type]
            date_of_birth=model.date_of_birth,  # type: ignore[arg-type]
            gender=model.gender,  # type: ignore[arg-type]
            national_id=model.national_id,  # type: ignore[arg-type]
            email=email,
            phone=phone,
            address=address,
            emergency_contact=emergency_contact,
            blood_type=model.blood_type,  # type: ignore[arg-type]
            allergies=model.allergies or [],  # type: ignore[arg-type]
            chronic_conditions=model.chronic_conditions or [],  # type: ignore[arg-type]
            current_medications=model.current_medications or [],  # type: ignore[arg-type]
            insurance=insurance,
            status=model.status or PatientStatus.ACTIVE,  # type: ignore[arg-type]
            last_vital_signs=last_vitals,
            last_vitals_date=model.last_vitals_date,  # type: ignore[arg-type]
            medical_record_number=model.medical_record_number,  # type: ignore[arg-type]
            notes=model.notes,  # type: ignore[arg-type]
        )

        if model.created_at:
            patient.created_at = model.created_at  # type: ignore[assignment]
        if model.updated_at:
            patient.updated_at = model.updated_at  # type: ignore[assignment]

        return patient

    def _to_model(self, patient: Patient) -> PatientModel:
        """Convert entity to model."""
        model = PatientModel(
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            national_id=patient.national_id,
            email=str(patient.email) if patient.email else None,
            phone=str(patient.phone) if patient.phone else None,
            blood_type=patient.blood_type,
            allergies=patient.allergies,
            chronic_conditions=patient.chronic_conditions,
            current_medications=patient.current_medications,
            status=patient.status,
            medical_record_number=patient.medical_record_number,
            notes=patient.notes,
        )

        if patient.address:
            model.address_street = patient.address.street
            model.address_city = patient.address.city
            model.address_state = patient.address.state
            model.address_postal_code = patient.address.postal_code
            model.address_country = patient.address.country

        if patient.emergency_contact:
            model.emergency_contact_name = patient.emergency_contact.name
            model.emergency_contact_relationship = patient.emergency_contact.relationship
            model.emergency_contact_phone = patient.emergency_contact.phone
            model.emergency_contact_email = patient.emergency_contact.email

        if patient.insurance:
            model.insurance_provider = patient.insurance.provider
            model.insurance_policy_number = patient.insurance.policy_number
            model.insurance_group_number = patient.insurance.group_number
            model.insurance_valid_until = patient.insurance.valid_until

        if patient.last_vital_signs:
            model.last_vitals = {
                "heart_rate": patient.last_vital_signs.heart_rate,
                "blood_pressure_systolic": patient.last_vital_signs.blood_pressure_systolic,
                "blood_pressure_diastolic": patient.last_vital_signs.blood_pressure_diastolic,
                "temperature": patient.last_vital_signs.temperature,
                "respiratory_rate": patient.last_vital_signs.respiratory_rate,
                "oxygen_saturation": patient.last_vital_signs.oxygen_saturation,
                "weight": patient.last_vital_signs.weight,
                "height": patient.last_vital_signs.height,
            }
            model.last_vitals_date = patient.last_vitals_date

        return model

    def _update_model(self, model: PatientModel, patient: Patient) -> None:
        """Update model from entity."""
        # Note: SQLAlchemy Column() syntax means Pyright sees Column objects at class level.
        model.first_name = patient.first_name  # type: ignore[assignment]
        model.last_name = patient.last_name  # type: ignore[assignment]
        model.date_of_birth = patient.date_of_birth  # type: ignore[assignment]
        model.gender = patient.gender  # type: ignore[assignment]
        model.national_id = patient.national_id  # type: ignore[assignment]
        model.email = str(patient.email) if patient.email else None  # type: ignore[assignment]
        model.phone = str(patient.phone) if patient.phone else None  # type: ignore[assignment]
        model.blood_type = patient.blood_type  # type: ignore[assignment]
        model.allergies = patient.allergies  # type: ignore[assignment]
        model.chronic_conditions = patient.chronic_conditions  # type: ignore[assignment]
        model.current_medications = patient.current_medications  # type: ignore[assignment]
        model.status = patient.status  # type: ignore[assignment]
        model.medical_record_number = patient.medical_record_number  # type: ignore[assignment]
        model.notes = patient.notes  # type: ignore[assignment]

        if patient.address:
            model.address_street = patient.address.street  # type: ignore[assignment]
            model.address_city = patient.address.city  # type: ignore[assignment]
            model.address_state = patient.address.state  # type: ignore[assignment]
            model.address_postal_code = patient.address.postal_code  # type: ignore[assignment]
            model.address_country = patient.address.country  # type: ignore[assignment]

        if patient.emergency_contact:
            model.emergency_contact_name = patient.emergency_contact.name  # type: ignore[assignment]
            model.emergency_contact_relationship = patient.emergency_contact.relationship  # type: ignore[assignment]
            model.emergency_contact_phone = patient.emergency_contact.phone  # type: ignore[assignment]
            model.emergency_contact_email = patient.emergency_contact.email  # type: ignore[assignment]

        if patient.insurance:
            model.insurance_provider = patient.insurance.provider  # type: ignore[assignment]
            model.insurance_policy_number = patient.insurance.policy_number  # type: ignore[assignment]
            model.insurance_group_number = patient.insurance.group_number  # type: ignore[assignment]
            model.insurance_valid_until = patient.insurance.valid_until  # type: ignore[assignment]

        if patient.last_vital_signs:
            model.last_vitals = {  # type: ignore[assignment]
                "heart_rate": patient.last_vital_signs.heart_rate,
                "blood_pressure_systolic": patient.last_vital_signs.blood_pressure_systolic,
                "blood_pressure_diastolic": patient.last_vital_signs.blood_pressure_diastolic,
                "temperature": patient.last_vital_signs.temperature,
                "respiratory_rate": patient.last_vital_signs.respiratory_rate,
                "oxygen_saturation": patient.last_vital_signs.oxygen_saturation,
                "weight": patient.last_vital_signs.weight,
                "height": patient.last_vital_signs.height,
            }
            model.last_vitals_date = patient.last_vitals_date  # type: ignore[assignment]
