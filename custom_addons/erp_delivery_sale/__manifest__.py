{
    "name": "ERP Delivery Sales Integration",
    "summary": "Create ERP delivery projects from confirmed sales orders",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "depends": ["erp_delivery_core", "sale_management"],
    "data": [
        "views/sale_order_views.xml",
        "views/project_project_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}