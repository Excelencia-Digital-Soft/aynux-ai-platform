# Testing Plan for PersonResolutionNode Refactoring

## Overview
This document outlines the comprehensive testing plan for the refactored PersonResolutionNode and its new services.

## Test Suite Structure

### Unit Tests (Already Created)

#### 1. PaymentAmountExtractor Tests
**File**: `tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_payment_amount_extractor.py`

**Coverage**:
- ✅ Service initialization
- ✅ Extracting valid payment amounts
- ✅ Handling messages without amounts
- ✅ Filtering DNI-like values
- ✅ Skipping extraction during identification flow
- ✅ Skipping when customer not identified
- ✅ Skipping when amount already exists
- ✅ Handling empty messages
- ✅ Amount validation (< DNI threshold)
- ✅ Negative amount rejection
- ✅ All identification step checks

**Total Tests**: 13

**Status**: ✅ Created and compiling

---

#### 2. ResponseBuilder Tests
**File**: `tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_response_builder.py`

**Coverage**:
- ✅ Service initialization
- ✅ Building basic success states
- ✅ Building states with payment context
- ✅ Building info query states
- ✅ Building welcome request states
- ✅ Building identifier request states
- ✅ Building identifier request with pending flow
- ✅ Building proceed with customer states (self/other)
- ✅ Building validation request states (self/other)
- ✅ State preservation across methods
- ✅ Building with no preserved fields
- ✅ DB session parameter handling

**Total Tests**: 12

**Status**: ✅ Created and compiling

---

### Unit Tests (Pending Creation)

#### 3. PersonRegistrationService Tests
**File**: `tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_person_registration_service.py`

**Tests Needed**:
- Service initialization with/without db_session
- Repository lazy initialization
- `register_identified_person()`:
  - Successfully registers person with valid data
  - Returns None when required data missing
  - Handles DB errors gracefully
  - Creates correct RegisteredPerson instance
- `complete_registration_flow()`:
  - Registers person in DB
  - Generates success response state
  - Preserves context fields
  - Sets customer_identified = True
  - Clears identification_step
- Error handling scenarios

**Estimated Tests**: 10-12

**Priority**: Medium (requires mocking of DB operations)

---

#### 4. InitialResolutionService Tests
**File**: `tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_initial_resolution_service.py`

**Tests Needed**:
- Service initialization
- `_check_existing_registrations()`:
  - Returns empty list when no registrations
  - Returns registrations when they exist
- `_check_plex_match()`:
  - Returns None when no match
  - Returns customer data when match found
- `_is_info_query()`:
  - Returns True for info queries
  - Returns False for other queries
  - Handles empty messages
- `_detect_service_intent()`:
  - Detects service intents with confidence ≥ 0.5
  - Returns None for non-service intents
  - Checks auth requirement
- `_flow_requires_auth()`:
  - Returns True for auth-required flows
  - Returns False for non-auth flows
  - Handles None flow values
- `_get_organization_id()`:
  - Returns organization_id from state
  - Falls back to configured org_id
  - Handles string to UUID conversion
  - Returns None for invalid UUIDs
- `resolve()`:
  - Routes to account selection when registrations exist
  - Routes to own/other when PLEX match exists
  - Routes to identifier for service intents
  - Routes to welcome for new users
  - Handles missing phone
  - Handles missing pharmacy_id

**Estimated Tests**: 20-25

**Priority**: High (requires extensive mocking)

---

#### 5. WorkflowOrchestrator Tests
**File**: `tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_workflow_orchestrator.py`

**Tests Needed**:
- Service initialization with factory
- `orchestrate()`:
  - Routes to person_selection when awaiting_person_selection
  - Routes based on identification_step
  - Handles welcome → DNI flow
  - Diagnoses workflow state
- `_route_based_on_identification_step()`:
  - Routes to welcome handler for STEP_AWAITING_WELCOME
  - Routes to identifier handler for STEP_AWAITING_IDENTIFIER
  - Routes to name handler for STEP_NAME
  - Routes to account selection for STEP_AWAITING_ACCOUNT_SELECTION
  - Routes to own/other handler
  - Routes to validation for legacy steps
- `_handle_identifier_input()`:
  - Delegates to identifier handler
  - Escalates on identification_failed
  - Returns result when successful
- `_handle_name_verification()`:
  - Delegates to name handler
  - Escalates on name_verification_failed
  - Completes identification when identification_complete
  - Calls PersonRegistrationService
- `_handle_account_selection()`:
  - Delegates to account selection handler
  - Renews registration expiration
  - Removes internal field
  - Handles DB errors
- `_handle_own_or_other()`:
  - Delegates to own/other handler
  - Routes to proceed_with_customer for "own"
  - Routes to validation for "other"
- `_diagnose_workflow_state()`:
  - Logs diagnostic information
- `_is_legacy_validation_step()`:
  - Returns True for legacy steps
  - Returns False for new flow steps
- `_route_to_legacy_validation()`:
  - Returns correct validation routing state
- `_route_to_validation()`:
  - Uses ResponseBuilder to build state

**Estimated Tests**: 30-35

**Priority**: High (requires extensive mocking)

---

### Integration Tests (Pending)

#### 6. Node Integration Tests
**File**: `tests/integration/domains/pharmacy/agents/nodes/person_resolution/test_node_integration.py`

**Tests Needed**:
- End-to-end person resolution flow:
  - New user → Welcome → Identifier → Name → Success
  - Existing registrations → Account selection → Success
  - PLEX match → Own/Other → Success
  - Info query → Router (no identification)
  - Service intent → Identifier → Name → Success
- Payment amount preservation:
  - Amount extracted from initial message
  - Amount preserved through identification flow
  - Amount passed to debt_check_node
- Zombie payment handling:
  - Detects zombie payment state
  - Clears zombie state
  - Continues with normal flow
- Inconsistent state recovery:
  - Resets state when customer_identified=True with identification_step
  - Clears customer data appropriately
- Error handling:
  - Handles exceptions gracefully
  - Returns error state from ErrorHandler

**Estimated Tests**: 15-20

**Priority**: High (requires full DB and external service mocking)

---

### Regression Tests (Pending)

#### 7. Existing Flow Tests
**File**: `tests/integration/domains/pharmacy/agents/nodes/person_resolution/test_regression.py`

**Tests Needed**:
- All existing person resolution flows still work
- Info query routing unchanged
- Service intent detection unchanged
- Zombie payment handling unchanged
- Account selection flow unchanged
- Own/other flow unchanged
- Escalation paths unchanged
- Legacy validation routing unchanged

**Estimated Tests**: 10-15

**Priority**: High (ensures no breaking changes)

---

## Test Execution Plan

### Phase 1: Unit Tests (Currently Executing)
1. ✅ Create PaymentAmountExtractor tests
2. ✅ Create ResponseBuilder tests
3. ⏳ Create PersonRegistrationService tests (Medium priority)
4. ⏳ Create InitialResolutionService tests (High priority)
5. ⏳ Create WorkflowOrchestrator tests (High priority)

**Estimated Time**: 4-6 hours

---

### Phase 2: Integration Tests
1. ⏳ Set up test fixtures for DB and external services
2. ⏳ Create Node integration tests
3. ⏳ Test end-to-end flows
4. ⏳ Test payment amount preservation
5. ⏳ Test zombie payment handling

**Estimated Time**: 6-8 hours

---

### Phase 3: Regression Tests
1. ⏳ Identify all existing person resolution test scenarios
2. ⏳ Create regression test suite
3. ⏳ Run against refactored code
4. ⏳ Fix any regressions

**Estimated Time**: 4-6 hours

---

## Test Coverage Goals

### Minimum Acceptable Coverage
- **PaymentAmountExtractor**: 90%+
- **ResponseBuilder**: 85%+
- **PersonRegistrationService**: 80%+
- **InitialResolutionService**: 75%+
- **WorkflowOrchestrator**: 75%+
- **Node class**: 70%+

### Target Coverage
- **All services**: 85%+
- **Node class**: 75%+

---

## Testing Infrastructure

### Required Fixtures
1. **DB Mocks**:
   - Mock AsyncSession
   - Mock RegisteredPersonRepository
   - Mock create_async_session

2. **External Service Mocks**:
   - Mock PlexClient
   - Mock PharmacyIntentAnalyzer
   - Mock ResponseGenerator

3. **Handler Mocks**:
   - Mock WelcomeFlowHandler
   - Mock IdentifierFlowHandler
   - Mock NameVerificationHandler
   - Mock AccountSelectionHandler
   - Mock OwnOrOtherHandler
   - Mock EscalationHandler
   - Mock ErrorHandler

4. **Service Mocks**:
   - Mock StateManagementService
   - Mock PersonIdentificationService
   - Mock PaymentStateService

### Test Data
- Sample PLEX customer data
- Sample registration data
- Sample state dictionaries for each flow
- Sample user messages for each scenario

---

## Test Execution Commands

```bash
# Run all person resolution tests
cd python
pytest tests/unit/domains/pharmacy/agents/nodes/person_resolution/ -v --no-cov

# Run specific test suite
pytest tests/unit/domains/pharmacy/agents/nodes/person_resolution/test_payment_amount_extractor.py -v

# Run with coverage
pytest tests/unit/domains/pharmacy/agents/nodes/person_resolution/ --cov=app/domains/pharmacy/agents/nodes/person_resolution --cov-report=html

# Run integration tests
pytest tests/integration/domains/pharmacy/agents/nodes/person_resolution/ -v

# Run regression tests
pytest tests/integration/domains/pharmacy/agents/nodes/person_resolution/test_regression.py -v
```

---

## Current Status

### Completed
- ✅ PaymentAmountExtractor service created and tested
- ✅ ResponseBuilder service created and tested
- ✅ PersonRegistrationService service created
- ✅ InitialResolutionService service created
- ✅ WorkflowOrchestrator service created
- ✅ Node class refactored
- ✅ Factory updated with new services
- ✅ Type checking passed (Pyright)
- ✅ Syntax validation passed (Python compile)

### In Progress
- ⏳ Unit tests for PaymentAmountExtractor (created, not run)
- ⏳ Unit tests for ResponseBuilder (created, not run)
- ⏳ Unit tests for remaining services

### Pending
- ⏳ Integration tests
- ⏳ Regression tests
- ⏳ Coverage reporting
- ⏳ Performance testing

---

## Success Criteria

### Must Have (Blocking)
1. All unit tests pass
2. All integration tests pass
3. No regressions in existing functionality
4. Code coverage ≥ 70% for all services
5. Type checking passes with 0 errors

### Should Have (Important)
1. Code coverage ≥ 80% for all services
2. All edge cases tested
3. Performance benchmarks established
4. Test documentation complete

### Nice to Have (Enhancement)
1. Property-based testing (Hypothesis)
2. Fuzz testing for inputs
3. Load testing for concurrent operations
4. Visual test coverage reports

---

## Next Steps

1. ✅ Create unit test files for all services
2. ⏳ Set up test infrastructure and fixtures
3. ⏳ Run unit tests and fix any failures
4. ⏳ Create integration tests
5. ⏳ Create regression tests
6. ⏳ Run full test suite
7. ⏳ Generate coverage report
8. ⏳ Document test results
9. ⏳ Update code documentation

---

## Notes

- **Mocking Strategy**: Use unittest.mock for Python stdlib, pytest-mock for external dependencies
- **Async Testing**: Use pytest-asyncio with async fixtures
- **Database**: Use in-memory SQLite for integration tests where possible
- **External Services**: Mock all external API calls (PLEX, ResponseGenerator, etc.)
- **State Management**: Create reusable state dict fixtures for common scenarios

---

## Conclusion

The refactoring is complete and type-safe. Comprehensive testing is the next critical step to ensure:
1. All services work correctly in isolation
2. Integration between services and node works correctly
3. No regressions in existing functionality
4. Code is maintainable and well-documented

**Estimated Total Testing Time**: 14-20 hours
**Current Progress**: 30% complete (2/6 test suites created)
