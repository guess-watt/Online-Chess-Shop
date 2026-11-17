from django.core.management.base import BaseCommand
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, Inventory
from inventory import services


class Command(BaseCommand):
    help = "Seeds ChessMart database with default stores, categories, products, and initial stock."

    def handle(self, *args, **options):
        self.stdout.write("Starting ChessMart data seeding...")

        # 1. Stores
        physical_store, _ = Store.objects.get_or_create(
            name="Downtown Physical Store",
            defaults={
                'store_type': Store.PHYSICAL,
                'address': '101 Grandmaster Way, Suite A, Metropolis',
                'is_active': True,
            }
        )
        online_store, _ = Store.objects.get_or_create(
            name="Online Webstore",
            defaults={
                'store_type': Store.ONLINE,
                'address': 'https://chessmart.example.com',
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Stores verified: '{physical_store.name}', '{online_store.name}'."))

        # 2. Categories
        categories_data = [
            ("Chess Boards", "Solid wood, folding, vinyl tournament, and silicone boards."),
            ("Chess Pieces", "Handcrafted wooden Staunton, triple-weighted plastic, and collector sets."),
            ("Chess Clocks", "FIDE-approved digital timers and classic mechanical tournament clocks."),
            ("Chess Books", "Openings, middle-game tactics, endgame manuals, and historical monographs."),
            ("Accessories", "Carrying bags, demonstration boards, scorebooks, and notation pens."),
        ]
        cat_map = {}
        for cat_name, desc in categories_data:
            cat, _ = Category.objects.get_or_create(name=cat_name, defaults={'description': desc, 'is_active': True})
            cat_map[cat_name] = cat
        self.stdout.write(self.style.SUCCESS("Categories verified."))

        # 3. Products
        products_data = [
            # (name, sku, category_name, cost, selling, threshold, phys_qty, online_qty, desc)
            (
                "DGT 2010 Digital Chess Clock", "CLK-DGT-2010", "Chess Clocks",
                Decimal("45.00"), Decimal("79.99"), 5, 8, 12,
                "Official FIDE clock with delay, byo-yomi, and multiple Fischer timing modes."
            ),
            (
                "DGT 3000 FIDE Approved Clock", "CLK-DGT-3000", "Chess Clocks",
                Decimal("65.00"), Decimal("109.99"), 4, 3, 4,
                "Premium tournament timer connecting directly with electronic DGT e-Boards."
            ),
            (
                "German Knight Staunton Wooden Pieces (3.75\")", "PCS-GER-375", "Chess Pieces",
                Decimal("60.00"), Decimal("119.50"), 5, 2, 1,  # Low stock: total 3 <= threshold 5!
                "Natural boxwood and ebonized sheesham pieces with heavy felted bases."
            ),
            (
                "Triple Weighted Regulation Plastic Pieces", "PCS-REG-PLAS", "Chess Pieces",
                Decimal("12.00"), Decimal("24.99"), 10, 25, 40,
                "Tournament standard 3.75\" king with extra queens. Durable impact-resistant plastic."
            ),
            (
                "Deluxe Walnut & Maple Wooden Chessboard (21\")", "BRD-WAL-21", "Chess Boards",
                Decimal("85.00"), Decimal("159.00"), 4, 4, 6,
                "Solid inlaid walnut and maple squares with satin lacquer protective finish."
            ),
            (
                "Silicone Roll-Up Tournament Board", "BRD-SIL-REG", "Chess Boards",
                Decimal("8.50"), Decimal("18.99"), 15, 30, 50,
                "Stain-resistant, spill-proof, lays completely flat without creases."
            ),
            (
                "100 Endgames You Must Know (Jesus de la Villa)", "BOK-ENDGM-100", "Chess Books",
                Decimal("13.50"), Decimal("24.95"), 6, 2, 2,  # Low stock: total 4 <= threshold 6!
                "Essential practical endgame theory required for competitive tournament players."
            ),
            (
                "Bobby Fischer Teaches Chess", "BOK-BF-TEACH", "Chess Books",
                Decimal("9.00"), Decimal("16.99"), 8, 14, 20,
                "Programmed learning method by the 11th World Chess Champion."
            ),
            (
                "Deluxe Padded Canvas Carrying Bag", "ACC-BAG-DLX", "Accessories",
                Decimal("14.00"), Decimal("29.99"), 5, 10, 15,
                "Padded compartments for roll-up board, pieces, scorebook, and digital clock."
            ),
            (
                "Hardcover Chess Scorebook (100 Games)", "ACC-SCR-BOOK", "Accessories",
                Decimal("4.50"), Decimal("9.99"), 12, 18, 30,
                "Spiral-bound scorebook with 100 game sheets and diagram tracking."
            ),
        ]

        for name, sku, cat_name, cost, selling, threshold, phys_qty, online_qty, desc in products_data:
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': cat_map[cat_name],
                    'cost_price': cost,
                    'selling_price': selling,
                    'low_stock_threshold': threshold,
                    'description': desc,
                    'is_active': True,
                }
            )

            # Ensure inventory records exist
            phys_inv, phys_created = Inventory.objects.get_or_create(
                product=product, store=physical_store, defaults={'quantity': 0}
            )
            online_inv, online_created = Inventory.objects.get_or_create(
                product=product, store=online_store, defaults={'quantity': 0}
            )

            # Adjust stock if freshly created or inventory is zero
            if phys_inv.quantity == 0 and phys_qty > 0:
                services.adjust_stock(
                    product=product,
                    store=physical_store,
                    quantity_delta=phys_qty,
                    movement_type='PURCHASE',
                    reason="Initial Seeding Stock - Physical Store"
                )
            if online_inv.quantity == 0 and online_qty > 0:
                services.adjust_stock(
                    product=product,
                    store=online_store,
                    quantity_delta=online_qty,
                    movement_type='PURCHASE',
                    reason="Initial Seeding Stock - Online Channel"
                )

        # 4. Customers & Sample Orders
        from customers.models import Customer
        from sales import services as sales_services
        from sales.models import Order

        c1, _ = Customer.objects.get_or_create(
            email="walkin@chessmart.local",
            defaults={'name': 'Walk-in Store Customer', 'customer_type': Customer.INDIVIDUAL, 'address': 'Counter'}
        )
        c2, _ = Customer.objects.get_or_create(
            email="contact@metropolitanyouthchess.org",
            defaults={'name': 'Metropolitan Youth Chess Club', 'customer_type': Customer.CLUB, 'phone': '555-0199', 'address': '45 Kingsway Blvd'}
        )
        c3, _ = Customer.objects.get_or_create(
            email="director@kasparovschool.edu",
            defaults={'name': 'Kasparov Chess Academy', 'customer_type': Customer.ACADEMY, 'phone': '555-0144', 'address': '12 Academy Court'}
        )

        if Order.objects.count() == 0:
            clock = Product.objects.get(sku="CLK-DGT-2010")
            board = Product.objects.get(sku="BRD-SIL-REG")
            pieces = Product.objects.get(sku="PCS-REG-PLAS")

            # Sample 1: Physical POS Sale
            sales_services.create_order(
                customer=c1,
                store=physical_store,
                items_data=[
                    {'product': clock, 'quantity': 1},
                    {'product': board, 'quantity': 2},
                ],
                notes="Walk-in cash counter sale",
                auto_confirm=True
            )

            # Sample 2: Online Club Order
            o2 = sales_services.create_order(
                customer=c2,
                store=online_store,
                items_data=[
                    {'product': board, 'quantity': 5},
                    {'product': pieces, 'quantity': 5},
                ],
                notes="Club tournament batch shipment",
                auto_confirm=False
            )
            sales_services.confirm_order(o2)

        self.stdout.write(self.style.SUCCESS("All products, inventory, customers, and orders seeded successfully!"))
