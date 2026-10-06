{
    "name": "ERP Delivery Quality Gate",
    "summary": "Validate quality score before ERP project Go-Live",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "depends": ["erp_delivery_core"],
    "data": [
        "security/ir.model.access.csv",
        "security/quality_gate_security.xml",
        "views/quality_gate_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}