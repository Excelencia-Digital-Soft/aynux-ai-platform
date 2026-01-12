# ============================================================================
# Tests for ResponseExtractor utility
# ============================================================================
"""Unit tests for ResponseExtractor.

Tests the utility class that extracts data from ExternalResponse objects
in a consistent manner across the medical appointments domain.
"""

from app.domains.medical_appointments.application.utils import ResponseExtractor


class TestAsDict:
    """Tests for ResponseExtractor.as_dict() method."""

    def test_as_dict_with_dict_input(self) -> None:
        """Should return dict directly when input is dict."""
        data = {"id": "123", "name": "Test"}
        result = ResponseExtractor.as_dict(data)
        assert result == {"id": "123", "name": "Test"}

    def test_as_dict_with_list_of_dicts(self) -> None:
        """Should return first dict when input is list of dicts."""
        data = [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]
        result = ResponseExtractor.as_dict(data)
        assert result == {"id": "1", "name": "First"}

    def test_as_dict_with_empty_list(self) -> None:
        """Should return empty dict when input is empty list."""
        result = ResponseExtractor.as_dict([])
        assert result == {}

    def test_as_dict_with_list_of_non_dicts(self) -> None:
        """Should return empty dict when list contains non-dicts."""
        data = ["string", 123, None]
        result = ResponseExtractor.as_dict(data)
        assert result == {}

    def test_as_dict_with_none(self) -> None:
        """Should return empty dict when input is None."""
        result = ResponseExtractor.as_dict(None)
        assert result == {}

    def test_as_dict_with_string(self) -> None:
        """Should return empty dict when input is string."""
        result = ResponseExtractor.as_dict("not a dict")
        assert result == {}

    def test_as_dict_with_number(self) -> None:
        """Should return empty dict when input is number."""
        result = ResponseExtractor.as_dict(42)
        assert result == {}

    def test_as_dict_with_nested_dict(self) -> None:
        """Should preserve nested structure."""
        data = {"patient": {"id": "123", "name": "Test"}, "status": "active"}
        result = ResponseExtractor.as_dict(data)
        assert result == data


class TestAsList:
    """Tests for ResponseExtractor.as_list() method."""

    def test_as_list_with_list_of_dicts(self) -> None:
        """Should return list directly when input is list of dicts."""
        data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        result = ResponseExtractor.as_list(data)
        assert result == data

    def test_as_list_with_single_dict(self) -> None:
        """Should wrap dict in list when input is single dict."""
        data = {"id": "123", "name": "Test"}
        result = ResponseExtractor.as_list(data)
        assert result == [{"id": "123", "name": "Test"}]

    def test_as_list_with_empty_list(self) -> None:
        """Should return empty list when input is empty list."""
        result = ResponseExtractor.as_list([])
        assert result == []

    def test_as_list_with_none(self) -> None:
        """Should return empty list when input is None."""
        result = ResponseExtractor.as_list(None)
        assert result == []

    def test_as_list_with_mixed_list(self) -> None:
        """Should filter out non-dict items from list."""
        data = [{"id": "1"}, "string", {"id": "2"}, 123, None]
        result = ResponseExtractor.as_list(data)
        assert result == [{"id": "1"}, {"id": "2"}]

    def test_as_list_with_string(self) -> None:
        """Should return empty list when input is string."""
        result = ResponseExtractor.as_list("not a list")
        assert result == []


class TestGetField:
    """Tests for ResponseExtractor.get_field() method."""

    def test_get_field_first_key_found(self) -> None:
        """Should return value from first matching key."""
        data = {"idPaciente": "123", "IdPaciente": "456"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
        assert result == "123"

    def test_get_field_second_key_found(self) -> None:
        """Should return value from second key if first not found."""
        data = {"IdPaciente": "456"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
        assert result == "456"

    def test_get_field_third_key_found(self) -> None:
        """Should check all keys in order."""
        data = {"id": "789"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente", "id")
        assert result == "789"

    def test_get_field_no_key_found(self) -> None:
        """Should return default when no key is found."""
        data = {"other": "value"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
        assert result == ""

    def test_get_field_custom_default(self) -> None:
        """Should return custom default when no key is found."""
        data = {"other": "value"}
        result = ResponseExtractor.get_field(
            data, "idPaciente", "IdPaciente", default="N/A"
        )
        assert result == "N/A"

    def test_get_field_converts_to_string(self) -> None:
        """Should convert non-string values to string."""
        data = {"id": 123}
        result = ResponseExtractor.get_field(data, "id")
        assert result == "123"
        assert isinstance(result, str)

    def test_get_field_skips_none_values(self) -> None:
        """Should skip None values and try next key."""
        data = {"idPaciente": None, "IdPaciente": "456"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
        assert result == "456"

    def test_get_field_skips_empty_string_values(self) -> None:
        """Should skip empty string values and try next key."""
        data = {"idPaciente": "", "IdPaciente": "456"}
        result = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
        assert result == "456"

    def test_get_field_with_empty_dict(self) -> None:
        """Should return default when dict is empty."""
        result = ResponseExtractor.get_field({}, "id")
        assert result == ""


class TestGetNested:
    """Tests for ResponseExtractor.get_nested() method."""

    def test_get_nested_single_level(self) -> None:
        """Should get value at single level."""
        data = {"name": "Test"}
        result = ResponseExtractor.get_nested(data, "name")
        assert result == "Test"

    def test_get_nested_two_levels(self) -> None:
        """Should get value at two levels deep."""
        data = {"patient": {"name": "Test"}}
        result = ResponseExtractor.get_nested(data, "patient", "name")
        assert result == "Test"

    def test_get_nested_three_levels(self) -> None:
        """Should get value at three levels deep."""
        data = {"patient": {"address": {"city": "San Juan"}}}
        result = ResponseExtractor.get_nested(data, "patient", "address", "city")
        assert result == "San Juan"

    def test_get_nested_missing_key(self) -> None:
        """Should return default when key is missing."""
        data = {"patient": {"name": "Test"}}
        result = ResponseExtractor.get_nested(data, "patient", "address")
        assert result is None

    def test_get_nested_custom_default(self) -> None:
        """Should return custom default when key is missing."""
        data = {"patient": {"name": "Test"}}
        result = ResponseExtractor.get_nested(
            data, "patient", "address", default="Unknown"
        )
        assert result == "Unknown"

    def test_get_nested_non_dict_intermediate(self) -> None:
        """Should return default when intermediate value is not dict."""
        data = {"patient": "not a dict"}
        result = ResponseExtractor.get_nested(data, "patient", "name")
        assert result is None

    def test_get_nested_empty_path(self) -> None:
        """Should return the data itself with empty path."""
        data = {"name": "Test"}
        result = ResponseExtractor.get_nested(data)
        assert result == data


class TestExtractItems:
    """Tests for ResponseExtractor.extract_items() method."""

    def test_extract_items_from_list(self) -> None:
        """Should return list directly when data is list."""
        data = [{"id": "1"}, {"id": "2"}]
        result = ResponseExtractor.extract_items(data, "items")
        assert result == data

    def test_extract_items_from_dict_with_key(self) -> None:
        """Should extract list from dict using provided key."""
        data = {"especialidades": [{"id": "1"}, {"id": "2"}]}
        result = ResponseExtractor.extract_items(data, "especialidades")
        assert result == [{"id": "1"}, {"id": "2"}]

    def test_extract_items_tries_multiple_keys(self) -> None:
        """Should try multiple keys in order."""
        data = {"items": [{"id": "1"}]}
        result = ResponseExtractor.extract_items(data, "especialidades", "items")
        assert result == [{"id": "1"}]

    def test_extract_items_wraps_single_dict_in_list(self) -> None:
        """Should wrap single dict value in list."""
        data = {"especialidades": {"id": "1", "name": "Test"}}
        result = ResponseExtractor.extract_items(data, "especialidades")
        assert result == [{"id": "1", "name": "Test"}]

    def test_extract_items_returns_dict_as_list_when_no_key_matches(self) -> None:
        """Should return dict wrapped in list when no key matches."""
        data = {"id": "1", "name": "Test"}
        result = ResponseExtractor.extract_items(data, "items", "datos")
        assert result == [{"id": "1", "name": "Test"}]

    def test_extract_items_filters_non_dicts_from_list(self) -> None:
        """Should filter out non-dict items from list."""
        data = [{"id": "1"}, "string", {"id": "2"}, 123]
        result = ResponseExtractor.extract_items(data, "items")
        assert result == [{"id": "1"}, {"id": "2"}]

    def test_extract_items_with_none(self) -> None:
        """Should return empty list when data is None."""
        result = ResponseExtractor.extract_items(None, "items")
        assert result == []

    def test_extract_items_with_empty_list(self) -> None:
        """Should return empty list when data is empty list."""
        result = ResponseExtractor.extract_items([], "items")
        assert result == []


class TestRealWorldScenarios:
    """Tests simulating real HCWeb API response patterns."""

    def test_patient_search_response(self) -> None:
        """Should handle patient search response format."""
        # HCWeb returns patients as a list
        response_data = [
            {
                "idPaciente": "12345",
                "dni": "30123456",
                "nombre": "Juan",
                "apellido": "Pérez",
                "celular": "2645551234",
            }
        ]

        patient = ResponseExtractor.as_dict(response_data)
        assert patient["idPaciente"] == "12345"

        patient_id = ResponseExtractor.get_field(
            patient, "idPaciente", "IdPaciente", "id"
        )
        assert patient_id == "12345"

    def test_specialties_response(self) -> None:
        """Should handle specialties response format."""
        # HCWeb returns specialties wrapped in a dict
        response_data = {
            "especialidades": [
                {"idEspecialidad": "1", "nombre": "Gastroenterología"},
                {"idEspecialidad": "2", "nombre": "Hepatología"},
            ]
        }

        specialties = ResponseExtractor.extract_items(
            response_data, "especialidades", "items"
        )
        assert len(specialties) == 2
        assert specialties[0]["nombre"] == "Gastroenterología"

    def test_providers_response_single_item(self) -> None:
        """Should handle single provider response (wrapped as dict)."""
        # Sometimes HCWeb returns single item not in a list
        response_data = {
            "prestadores": {"idPrestador": "123", "nombreCompleto": "Dr. García"}
        }

        providers = ResponseExtractor.extract_items(response_data, "prestadores")
        assert len(providers) == 1
        assert providers[0]["nombreCompleto"] == "Dr. García"

    def test_appointment_creation_response(self) -> None:
        """Should handle appointment creation response."""
        response_data = {
            "idTurno": "999",
            "estado": "pendiente",
            "fecha": "15/01/2026",
            "hora": "10:30",
        }

        appointment = ResponseExtractor.as_dict(response_data)
        appointment_id = ResponseExtractor.get_field(
            appointment, "idTurno", "id_turno", "id"
        )
        assert appointment_id == "999"

    def test_empty_response_handling(self) -> None:
        """Should handle empty/null responses gracefully."""
        # Various empty response patterns
        assert ResponseExtractor.as_dict(None) == {}
        assert ResponseExtractor.as_dict({}) == {}
        assert ResponseExtractor.as_list(None) == []
        assert ResponseExtractor.extract_items(None, "items") == []
        assert ResponseExtractor.get_field({}, "id", default="N/A") == "N/A"
