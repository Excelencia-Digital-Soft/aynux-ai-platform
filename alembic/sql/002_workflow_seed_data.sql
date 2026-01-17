-- ============================================================================
-- Workflow Seed Data - Builtin Node Definitions
-- ============================================================================
-- Seeds the workflow schema with builtin node definitions for medical
-- appointments workflow. These are the default nodes available to all
-- institutions.
-- ============================================================================

-- ============================================================================
-- Builtin Node Definitions
-- ============================================================================

INSERT INTO workflow.node_definitions (
    node_key, node_type, python_class, python_module,
    display_name, description, icon, color, category,
    config_schema, default_config, inputs, outputs, is_builtin, is_active
) VALUES
-- Entry/Routing Node
(
    'router',
    'routing',
    'RouterNode',
    'app.domains.medical_appointments.agents.nodes.router',
    'Router',
    'Entry point node that detects user intent and routes to appropriate node',
    'pi-directions',
    '#3B82F6',
    'routing',
    '{"type": "object", "properties": {"intents": {"type": "array"}}}',
    '{}',
    '["messages", "user_phone"]',
    '["detected_intent", "next_node"]',
    TRUE,
    TRUE
),
-- Greeting Node
(
    'greeting',
    'conversation',
    'GreetingNode',
    'app.domains.medical_appointments.agents.nodes.greeting',
    'Greeting',
    'Sends welcome message to the user',
    'pi-comments',
    '#10B981',
    'conversation',
    '{"type": "object", "properties": {"message": {"type": "string"}}}',
    '{"message": "Hola, bienvenido. ¿En qué puedo ayudarte?"}',
    '["user_phone"]',
    '["messages"]',
    TRUE,
    TRUE
),
-- Patient Identification Node
(
    'patient_identification',
    'conversation',
    'PatientIdentificationNode',
    'app.domains.medical_appointments.agents.nodes.patient_identification',
    'Patient Identification',
    'Requests and validates patient DNI for identification',
    'pi-id-card',
    '#8B5CF6',
    'booking',
    '{"type": "object", "properties": {"max_retries": {"type": "integer", "default": 3}}}',
    '{"max_retries": 3}',
    '["messages", "user_phone"]',
    '["patient_document", "patient_data", "is_registered"]',
    TRUE,
    TRUE
),
-- Patient Registration Node
(
    'patient_registration',
    'conversation',
    'PatientRegistrationNode',
    'app.domains.medical_appointments.agents.nodes.patient_registration',
    'Patient Registration',
    'Registers a new patient in the system',
    'pi-user-plus',
    '#F59E0B',
    'booking',
    '{"type": "object", "properties": {"required_fields": {"type": "array"}}}',
    '{"required_fields": ["nombre", "apellido", "dni", "telefono"]}',
    '["messages", "user_phone", "patient_document"]',
    '["patient_data", "is_registered"]',
    TRUE,
    TRUE
),
-- Specialty Selection Node
(
    'specialty_selection',
    'conversation',
    'SpecialtySelectionNode',
    'app.domains.medical_appointments.agents.nodes.specialty_selection',
    'Specialty Selection',
    'Shows available specialties and handles user selection',
    'pi-heart',
    '#EC4899',
    'booking',
    '{"type": "object", "properties": {"filter_specialties": {"type": "array"}}}',
    '{}',
    '["messages", "patient_data"]',
    '["selected_specialty", "specialties_list"]',
    TRUE,
    TRUE
),
-- Provider Selection Node
(
    'provider_selection',
    'conversation',
    'ProviderSelectionNode',
    'app.domains.medical_appointments.agents.nodes.provider_selection',
    'Provider Selection',
    'Shows available providers/doctors and handles user selection',
    'pi-user',
    '#14B8A6',
    'booking',
    '{"type": "object", "properties": {}}',
    '{}',
    '["messages", "patient_data", "selected_specialty"]',
    '["selected_provider", "providers_list"]',
    TRUE,
    TRUE
),
-- Date Selection Node
(
    'date_selection',
    'conversation',
    'DateSelectionNode',
    'app.domains.medical_appointments.agents.nodes.date_selection',
    'Date Selection',
    'Shows available dates and handles user selection',
    'pi-calendar',
    '#6366F1',
    'booking',
    '{"type": "object", "properties": {"max_days_ahead": {"type": "integer", "default": 30}}}',
    '{"max_days_ahead": 30}',
    '["messages", "patient_data", "selected_provider"]',
    '["selected_date", "available_dates"]',
    TRUE,
    TRUE
),
-- Time Selection Node
(
    'time_selection',
    'conversation',
    'TimeSelectionNode',
    'app.domains.medical_appointments.agents.nodes.time_selection',
    'Time Selection',
    'Shows available time slots and handles user selection',
    'pi-clock',
    '#0EA5E9',
    'booking',
    '{"type": "object", "properties": {}}',
    '{}',
    '["messages", "patient_data", "selected_provider", "selected_date"]',
    '["selected_time", "available_times"]',
    TRUE,
    TRUE
),
-- Booking Confirmation Node
(
    'booking_confirmation',
    'conversation',
    'BookingConfirmationNode',
    'app.domains.medical_appointments.agents.nodes.booking_confirmation',
    'Booking Confirmation',
    'Shows appointment summary and confirms the booking',
    'pi-check-circle',
    '#22C55E',
    'booking',
    '{"type": "object", "properties": {"require_confirmation": {"type": "boolean", "default": true}}}',
    '{"require_confirmation": true}',
    '["messages", "patient_data", "selected_specialty", "selected_provider", "selected_date", "selected_time"]',
    '["appointment_id", "booking_confirmed"]',
    TRUE,
    TRUE
),
-- Appointment Management Node
(
    'appointment_management',
    'conversation',
    'AppointmentManagementNode',
    'app.domains.medical_appointments.agents.nodes.appointment_management',
    'Appointment Management',
    'Allows users to view and manage their appointments',
    'pi-list',
    '#64748B',
    'management',
    '{"type": "object", "properties": {}}',
    '{}',
    '["messages", "patient_data"]',
    '["appointments_list"]',
    TRUE,
    TRUE
),
-- Reschedule Node
(
    'reschedule',
    'conversation',
    'RescheduleNode',
    'app.domains.medical_appointments.agents.nodes.reschedule',
    'Reschedule',
    'Handles appointment rescheduling',
    'pi-calendar-times',
    '#F97316',
    'management',
    '{"type": "object", "properties": {}}',
    '{}',
    '["messages", "patient_data", "appointment_id"]',
    '["rescheduled"]',
    TRUE,
    TRUE
),
-- Fallback Node
(
    'fallback',
    'routing',
    'FallbackNode',
    'app.domains.medical_appointments.agents.nodes.fallback',
    'Fallback',
    'Handles unrecognized inputs and error recovery',
    'pi-exclamation-triangle',
    '#EF4444',
    'routing',
    '{"type": "object", "properties": {"max_retries": {"type": "integer", "default": 3}}}',
    '{"max_retries": 3}',
    '["messages", "error_count"]',
    '["error_count", "next_node"]',
    TRUE,
    TRUE
),
-- Human Handoff Node (NEW)
(
    'human_handoff',
    'routing',
    'HumanHandoffNode',
    'app.domains.medical_appointments.agents.nodes.human_handoff',
    'Human Handoff',
    'Transfers conversation to human agent',
    'pi-user-cog',
    '#DC2626',
    'routing',
    '{"type": "object", "properties": {"message": {"type": "string"}, "transfer_to": {"type": "string"}}}',
    '{"message": "Te estoy transfiriendo con un agente humano.", "transfer_to": "default"}',
    '["messages", "patient_data", "selected_specialty"]',
    '["transferred_to_human"]',
    TRUE,
    TRUE
);

-- ============================================================================
-- Global Message Templates
-- ============================================================================

INSERT INTO workflow.message_templates (
    institution_config_id, template_key, template_type,
    display_name, description, content, buttons, placeholders, language, is_active
) VALUES
-- Reminder Templates (Global)
(
    NULL,
    'reminder_7_days',
    'reminder',
    'Recordatorio 7 días antes',
    'Reminder sent 7 days before appointment',
    'Hola {patient_name}, te recordamos que tienes un turno programado para el {appointment_date} a las {appointment_time} con {provider_name} en {institution_name}. ¿Confirmas tu asistencia?',
    '[{"id": "confirm", "title": "Confirmar"}, {"id": "reschedule", "title": "Reprogramar"}, {"id": "cancel", "title": "Cancelar"}]',
    '["patient_name", "appointment_date", "appointment_time", "provider_name", "institution_name"]',
    'es',
    TRUE
),
(
    NULL,
    'reminder_24_hours',
    'reminder',
    'Recordatorio 24 horas antes',
    'Reminder sent 24 hours before appointment',
    'Hola {patient_name}, te recordamos que mañana tienes turno a las {appointment_time} con {provider_name}. No olvides traer tu documento de identidad.',
    '[{"id": "confirm", "title": "Confirmo"}, {"id": "cancel", "title": "Cancelar"}]',
    '["patient_name", "appointment_time", "provider_name"]',
    'es',
    TRUE
),
-- Confirmation Templates (Global)
(
    NULL,
    'booking_confirmed',
    'confirmation',
    'Turno Confirmado',
    'Confirmation message after booking',
    '¡Turno confirmado! {patient_name}, tu turno para {specialty_name} con {provider_name} quedó reservado para el {appointment_date} a las {appointment_time}. Te enviaremos un recordatorio antes de la fecha.',
    '[]',
    '["patient_name", "specialty_name", "provider_name", "appointment_date", "appointment_time"]',
    'es',
    TRUE
),
(
    NULL,
    'booking_cancelled',
    'confirmation',
    'Turno Cancelado',
    'Confirmation message after cancellation',
    'Tu turno del {appointment_date} a las {appointment_time} ha sido cancelado correctamente. ¿Deseas programar un nuevo turno?',
    '[{"id": "new_appointment", "title": "Nuevo turno"}]',
    '["appointment_date", "appointment_time"]',
    'es',
    TRUE
),
-- Human Handoff Templates (Global)
(
    NULL,
    'human_handoff_specialty',
    'handoff',
    'Derivación por Especialidad',
    'Message when transferring to human for specialty',
    'Para agendar un turno de {specialty_name} necesitamos derivarte con un agente. Te estamos transfiriendo, por favor espera un momento.',
    '[]',
    '["specialty_name"]',
    'es',
    TRUE
),
(
    NULL,
    'human_handoff_error',
    'handoff',
    'Derivación por Error',
    'Message when transferring to human due to errors',
    'Parece que estamos teniendo dificultades para ayudarte. Te estamos transfiriendo con un agente humano para brindarte mejor asistencia.',
    '[]',
    '[]',
    'es',
    TRUE
);
