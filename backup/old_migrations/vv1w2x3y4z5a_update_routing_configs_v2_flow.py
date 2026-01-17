"""Update routing configs for pharmacy_flujo_mejorado_v2.

Revision ID: vv1w2x3y4z5a
Revises: uu0v1w2x3y4z
Create Date: 2026-01-13

Updates routing configurations to match python/docs/pharmacy_flujo_mejorado_v2.md:

Main Menu (3 options):
1. Consultar deuda -> debt_manager (SHOW_DEBT)
2. Pagar deuda -> debt_manager (PAY_DEBT_MENU - shows debt summary first)
3. Ver otra cuenta -> account_switcher (CHANGE_ACCOUNT)

Changes:
- Update menu_option "2" from payment_link to pay_debt_menu intent
- Update menu_option "3" from payment_history to switch_account
- Disable menu_options 4, 5, 6, 0 (not in v2 flow)
- Add btn_ver_detalle button mapping for INVOICE_DETAIL flow
- Add btn_volver_menu button mapping

Note: The document specifies info_farmacia is accessible via natural language,
not via a menu option.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "vv1w2x3y4z5a"
down_revision: Union[str, Sequence[str], None] = "uu0v1w2x3y4z"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update routing configs for v2 flow."""

    # ==========================================================================
    # 0. Add natural language global keywords for flow interruption
    # Per doc: User can say "consultar deuda", "pagar deuda", etc. at any point
    # ==========================================================================

    # "consultar deuda" / "ver deuda" / "mi deuda" -> debt_query
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, metadata, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'global_keyword',
            'consultar deuda',
            'debt_query',
            'debt_manager',
            85,
            true,
            false,
            '{"aliases": ["ver deuda", "mi deuda", "cuanto debo", "cuánto debo", "deuda", "saldo"]}'::jsonb,
            'Consultar deuda',
            'Natural language: consultar deuda - redirects to SHOW_DEBT flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            metadata = EXCLUDED.metadata
    """)

    # "pagar deuda" / "quiero pagar" -> pay_debt_menu
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, metadata, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'global_keyword',
            'pagar deuda',
            'pay_debt_menu',
            'debt_manager',
            85,
            true,
            false,
            '{"aliases": ["quiero pagar", "pagar", "hacer pago", "generar pago"]}'::jsonb,
            'Pagar deuda',
            'Natural language: pagar deuda - redirects to PAY_DEBT_MENU flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            metadata = EXCLUDED.metadata
    """)

    # "ver otra cuenta" / "cambiar cuenta" -> switch_account
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, metadata, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'global_keyword',
            'otra cuenta',
            'switch_account',
            'account_switcher',
            85,
            true,
            false,
            '{"aliases": ["ver otra cuenta", "cambiar cuenta", "otra persona", "cambiar persona"]}'::jsonb,
            'Ver otra cuenta',
            'Natural language: ver otra cuenta - redirects to CHANGE_ACCOUNT flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            metadata = EXCLUDED.metadata
    """)

    # ==========================================================================
    # 1. Update menu_option "2" from payment_link to pay_debt_menu
    # According to doc: "Pagar deuda" shows debt summary first, then payment options
    # ==========================================================================
    op.execute("""
        UPDATE core.routing_configs
        SET target_intent = 'pay_debt_menu',
            target_node = 'debt_manager',
            display_name = 'Pagar deuda (Menu 2)',
            description = 'Shows debt summary first, then payment options (PAY_DEBT_MENU flow)'
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value = '2'
          AND organization_id IS NULL
    """)

    # ==========================================================================
    # 2. Update menu_option "3" from payment_history to switch_account
    # According to doc: Option 3 is "Ver otra cuenta"
    # ==========================================================================
    op.execute("""
        UPDATE core.routing_configs
        SET target_intent = 'switch_account',
            target_node = 'account_switcher',
            display_name = 'Ver otra cuenta (Menu 3)',
            description = 'Change to another registered account'
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value = '3'
          AND organization_id IS NULL
    """)

    # ==========================================================================
    # 3. Disable menu_options 4, 5, 6, 0 (not in v2 flow)
    # Info farmacia, help, exit are accessible via natural language or global keywords
    # ==========================================================================
    op.execute("""
        UPDATE core.routing_configs
        SET is_enabled = false,
            description = 'Disabled - not in v2 flow (accessible via natural language)'
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value IN ('4', '5', '6', '0')
          AND organization_id IS NULL
    """)

    # ==========================================================================
    # 4. Add button mapping for "Ver detalle de factura" (INVOICE_DETAIL flow)
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_ver_detalle',
            'view_invoice_detail',
            'debt_manager',
            50,
            true,
            false,
            'Ver detalle de factura',
            'Shows invoice detail (number, date, amount) - INVOICE_DETAIL flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 5. Add button mapping for "Volver al menu"
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_volver_menu',
            'show_menu',
            'main_menu_node',
            50,
            false,
            true,
            'Volver al menu',
            'Returns to main menu, clears current flow context'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            clears_context = EXCLUDED.clears_context,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 6. Add button mapping for "Pagar deuda completa" (from SHOW_DEBT)
    # Different from btn_pay_full which is for PAY_DEBT_MENU context
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_pagar_completo',
            'pay_full',
            'payment_processor',
            50,
            true,
            false,
            'Pagar deuda completa',
            'Full payment from debt view - generates payment link'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 7. Add button mapping for "Pago parcial" (from SHOW_DEBT)
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_pago_parcial',
            'pay_partial',
            'payment_processor',
            50,
            true,
            false,
            'Pago parcial',
            'Partial payment from debt view - asks for amount'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 8. Add intent global keyword for "info farmacia" (via natural language)
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, metadata, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'global_keyword',
            'info',
            'info_query',
            'info_node',
            80,
            false,
            false,
            '{"aliases": ["información", "informacion", "información de la farmacia", "horario", "direccion", "dirección", "telefono", "teléfono"]}'::jsonb,
            'Información de farmacia',
            'Pharmacy info via natural language - accessible anytime'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            metadata = EXCLUDED.metadata,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 9. Add button mappings for main menu WhatsApp buttons
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_consultar_deuda',
            'debt_query',
            'debt_manager',
            50,
            true,
            false,
            'Consultar deuda (menu)',
            'Main menu button: Consultar deuda -> SHOW_DEBT flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_pagar_deuda',
            'pay_debt_menu',
            'debt_manager',
            50,
            true,
            false,
            'Pagar deuda (menu)',
            'Main menu button: Pagar deuda -> PAY_DEBT_MENU flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_otra_cuenta',
            'switch_account',
            'account_switcher',
            50,
            true,
            false,
            'Ver otra cuenta (menu)',
            'Main menu button: Ver otra cuenta -> CHANGE_ACCOUNT flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)

    # ==========================================================================
    # 10. Add button mapping for INVOICE_DETAIL: Volver a deuda
    # ==========================================================================
    op.execute("""
        INSERT INTO core.routing_configs
        (organization_id, domain_key, config_type, trigger_value, target_intent,
         target_node, priority, requires_auth, clears_context, display_name, description)
        VALUES (
            NULL,
            'pharmacy',
            'button_mapping',
            'btn_volver_deuda',
            'debt_query',
            'debt_manager',
            50,
            true,
            false,
            'Volver a deuda',
            'INVOICE_DETAIL button: Return to SHOW_DEBT flow'
        )
        ON CONFLICT (organization_id, domain_key, config_type, trigger_value) DO UPDATE
        SET target_intent = EXCLUDED.target_intent,
            target_node = EXCLUDED.target_node,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description
    """)


def downgrade() -> None:
    """Revert routing configs to original state."""

    # Restore menu_option "2" to original
    op.execute("""
        UPDATE core.routing_configs
        SET target_intent = 'payment_link',
            target_node = 'payment_processor',
            display_name = 'Payment Link (Menu 2)',
            description = NULL
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value = '2'
          AND organization_id IS NULL
    """)

    # Restore menu_option "3" to original
    op.execute("""
        UPDATE core.routing_configs
        SET target_intent = 'payment_history',
            target_node = 'payment_history_node',
            display_name = 'Payment History (Menu 3)',
            description = NULL
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value = '3'
          AND organization_id IS NULL
    """)

    # Re-enable menu_options 4, 5, 6, 0
    op.execute("""
        UPDATE core.routing_configs
        SET is_enabled = true,
            description = NULL
        WHERE domain_key = 'pharmacy'
          AND config_type = 'menu_option'
          AND trigger_value IN ('4', '5', '6', '0')
          AND organization_id IS NULL
    """)

    # Remove added button mappings
    op.execute("""
        DELETE FROM core.routing_configs
        WHERE domain_key = 'pharmacy'
          AND config_type = 'button_mapping'
          AND trigger_value IN ('btn_ver_detalle', 'btn_volver_menu', 'btn_pagar_completo', 'btn_pago_parcial')
          AND organization_id IS NULL
    """)

    # Remove info global keyword
    op.execute("""
        DELETE FROM core.routing_configs
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value = 'info'
          AND organization_id IS NULL
    """)

    # Remove natural language global keywords
    op.execute("""
        DELETE FROM core.routing_configs
        WHERE domain_key = 'pharmacy'
          AND config_type = 'global_keyword'
          AND trigger_value IN ('consultar deuda', 'pagar deuda', 'otra cuenta')
          AND organization_id IS NULL
    """)

    # Remove main menu and flow button mappings
    op.execute("""
        DELETE FROM core.routing_configs
        WHERE domain_key = 'pharmacy'
          AND config_type = 'button_mapping'
          AND trigger_value IN ('btn_consultar_deuda', 'btn_pagar_deuda', 'btn_otra_cuenta', 'btn_volver_deuda')
          AND organization_id IS NULL
    """)
