{
    "name": "ERP Platform Delivery Core",
    "summary": "Core data models for ERP implementation delivery",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "depends": ["base", "project", "mail"],
    "data": [
        "data/erp_delivery_sequence.xml",
        "security/erp_security.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}