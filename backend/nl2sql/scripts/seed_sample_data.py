"""
scripts/seed_sample_data.py
────────────────────────────────────────────────────────────────────────────
Seeds a realistic e-commerce warehouse for NL2SQL evaluation.

The seed is idempotent at the table-family level: if core business tables
already contain rows, the script skips work.
"""

import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from faker import Faker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.connection import db_session, init_db
from app.models.tables import (
    Attribute,
    Cart,
    CartItem,
    Category,
    Coupon,
    Customer,
    CustomerAddress,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductAttributeValue,
    ProductImage,
    ProductReview,
    ProductVariant,
    Seller,
    Shipment,
    Wishlist,
)

fake = Faker("en_IN")
random.seed(42)
Faker.seed(42)


CATEGORY_FAMILIES = {
    "Electronics": ["Mobile Phones", "Laptops", "Headphones", "Smart Watches", "Tablets"],
    "Fashion": ["Men Shirts", "Women Dresses", "Sneakers", "Jackets", "Bags"],
    "Home": ["Sofas", "Dining Tables", "Cookware", "Bedsheets", "Storage Boxes"],
    "Beauty": ["Skin Care", "Makeup", "Hair Care", "Fragrances", "Grooming Kits"],
    "Sports": ["Running Shoes", "Yoga Mats", "Dumbbells", "Cycling Gear", "Cricket Kits"],
    "Books": ["Fiction", "Non-Fiction", "Academic", "Children", "Comics"],
    "Grocery": ["Snacks", "Beverages", "Dry Fruits", "Organic Staples", "Breakfast"],
    "Appliances": ["Mixers", "Air Fryers", "Vacuum Cleaners", "Fans", "Water Purifiers"],
}

BRANDS = [
    "Nova", "UrbanTrail", "PixelNest", "Aster", "BlueArc", "VividKart", "Nimbus",
    "TerraHome", "GlowUp", "SwiftRun", "Heritage", "ZenLife", "CraftHub", "EverPeak",
]
COLORS = ["Black", "Blue", "Red", "Green", "Silver", "White", "Grey", "Pink", "Navy", "Beige"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL", "128GB", "256GB", "512GB", "One Size"]
ORDER_STATUSES = ["placed", "confirmed", "processing", "shipped", "delivered", "cancelled", "returned"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet", "cash_on_delivery"]
PAYMENT_GATEWAYS = ["Razorpay", "PayU", "Stripe", "PhonePe", "Cashfree"]
PAYMENT_STATUSES = ["pending", "paid", "failed", "refunded"]
SHIPPING_STATUSES = ["packed", "in_transit", "out_for_delivery", "delivered", "returned"]
ADDRESS_TYPES = ["home", "work"]
PRODUCT_STATUS = ["active", "active", "active", "inactive"]
CUSTOMER_STATUS = ["active", "active", "active", "inactive", "blocked"]
ATTRIBUTE_BASE = [
    "RAM", "Storage", "Material", "Fabric", "Battery", "Screen Size", "Warranty",
    "Sleeve Type", "Fit", "Heel Type", "Capacity", "Flavor", "Organic", "Voltage",
    "Waterproof", "Pattern", "Occasion", "Processor", "Refresh Rate", "Connectivity",
]


def money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def random_recent_datetime(days: int = 365) -> datetime:
    return datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def random_birth_date() -> date:
    start = date(1975, 1, 1)
    end = date(2005, 12, 31)
    offset = random.randint(0, (end - start).days)
    return start + timedelta(days=offset)


def build_product_name(category_name: str, brand: str) -> str:
    if "Mobile" in category_name:
        return f"{brand} {fake.word().title()} 5G Smartphone"
    if "Laptop" in category_name:
        return f"{brand} {fake.word().title()} Pro Laptop"
    if "Headphones" in category_name:
        return f"{brand} Wireless Noise Cancelling Headphones"
    if "Watch" in category_name:
        return f"{brand} Smart Fitness Watch"
    if "Shirt" in category_name:
        return f"{brand} Cotton Casual Shirt"
    if "Dress" in category_name:
        return f"{brand} Floral Midi Dress"
    if "Sneakers" in category_name:
        return f"{brand} Everyday Sneakers"
    if "Cookware" in category_name:
        return f"{brand} Non-Stick Cookware Set"
    if "Skin Care" in category_name:
        return f"{brand} Vitamin C Face Serum"
    if "Running Shoes" in category_name:
        return f"{brand} Marathon Running Shoes"
    if "Fiction" in category_name:
        return f"{fake.color_name()} {fake.word().title()} Stories"
    if "Beverages" in category_name:
        return f"{brand} Cold Brew Coffee Pack"
    if "Air Fryers" in category_name:
        return f"{brand} Digital Air Fryer"
    return f"{brand} {category_name.rstrip('s')} {fake.word().title()}"


def build_variant_name(product_name: str, color: str, size: str) -> str:
    return f"{product_name} - {color} / {size}"


def build_category_rows(db):
    categories = []
    root_categories = []
    for root_name, children in CATEGORY_FAMILIES.items():
        root = Category(category_name=root_name, slug=root_name.lower().replace(" ", "-"))
        db.add(root)
        db.flush()
        categories.append(root)
        root_categories.append(root)
        for child_name in children:
            child = Category(
                parent_category_id=root.category_id,
                category_name=child_name,
                slug=f"{root_name.lower().replace(' ', '-')}-{child_name.lower().replace(' ', '-')}",
            )
            db.add(child)
            db.flush()
            categories.append(child)

    while len(categories) < 100:
        parent = random.choice(root_categories)
        name = f"{parent.category_name} {fake.word().title()} {len(categories)}"
        category = Category(
            parent_category_id=parent.category_id,
            category_name=name,
            slug=name.lower().replace(" ", "-"),
        )
        db.add(category)
        db.flush()
        categories.append(category)
    return categories


def build_attribute_rows(db):
    names = ATTRIBUTE_BASE[:]
    while len(names) < 100:
        names.append(f"{fake.word().title()} Spec {len(names) + 1}")

    attributes = []
    for name in names[:100]:
        attribute = Attribute(attribute_name=name)
        db.add(attribute)
        db.flush()
        attributes.append(attribute)
    return attributes


def seed() -> None:
    init_db()

    with db_session() as db:
        existing = {
            "customers": db.query(Customer).count(),
            "products": db.query(Product).count(),
            "orders": db.query(Order).count(),
        }
        if any(existing.values()):
            print(
                "ℹ️ Sample data already present — skipping seed "
                f"(customers={existing['customers']}, products={existing['products']}, orders={existing['orders']})."
            )
            return

        categories = build_category_rows(db)
        attributes = build_attribute_rows(db)

        sellers = []
        for i in range(100):
            seller = Seller(
                business_name=f"{fake.company()} Marketplace",
                seller_name=fake.name(),
                email=f"seller{i}@example.com",
                phone=fake.msisdn()[:13],
                gst_number=f"GST{100000 + i}",
                rating=money(random.uniform(3.2, 4.9)),
            )
            db.add(seller)
            db.flush()
            sellers.append(seller)

        customers = []
        addresses = []
        for i in range(150):
            first = fake.first_name()
            last = fake.last_name()
            customer = Customer(
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}.{i}@example.com",
                phone=f"9{100000000 + i:09d}",
                password_hash=fake.sha256(),
                gender=random.choice(["male", "female", "other"]),
                date_of_birth=random_birth_date(),
                is_email_verified=random.random() < 0.8,
                is_phone_verified=random.random() < 0.75,
                status=random.choice(CUSTOMER_STATUS),
                created_at=random_recent_datetime(1000),
                updated_at=random_recent_datetime(200),
            )
            db.add(customer)
            db.flush()
            customers.append(customer)

            customer_address_count = 2 if i < 120 else 1
            default_assigned = False
            for _ in range(customer_address_count):
                address = CustomerAddress(
                    customer_id=customer.customer_id,
                    full_name=f"{first} {last}",
                    phone=customer.phone,
                    address_line1=fake.street_address(),
                    address_line2=f"Near {fake.company()}",
                    landmark=fake.company(),
                    city=fake.city(),
                    state=fake.state(),
                    country="India",
                    postal_code=fake.postcode(),
                    address_type=random.choice(ADDRESS_TYPES),
                    is_default=not default_assigned,
                    created_at=random_recent_datetime(500),
                )
                db.add(address)
                db.flush()
                addresses.append(address)
                default_assigned = True

        products = []
        variants = []
        images = []
        attribute_values = []
        leaf_categories = [category for category in categories if category.parent_category_id]
        for i in range(180):
            category = random.choice(leaf_categories)
            seller = random.choice(sellers)
            brand = random.choice(BRANDS)
            product_name = build_product_name(category.category_name, brand)
            product = Product(
                seller_id=seller.seller_id,
                category_id=category.category_id,
                product_name=product_name,
                slug=f"{product_name.lower().replace(' ', '-')}-{i}",
                short_description=fake.sentence(nb_words=10),
                description=fake.paragraph(nb_sentences=4),
                brand=brand,
                status=random.choice(PRODUCT_STATUS),
                created_at=random_recent_datetime(600),
                updated_at=random_recent_datetime(100),
            )
            db.add(product)
            db.flush()
            products.append(product)

            product_attributes = random.sample(attributes, 3)
            for attribute in product_attributes:
                pav = ProductAttributeValue(
                    product_id=product.product_id,
                    attribute_id=attribute.attribute_id,
                    attribute_value=random.choice(["8GB", "128GB", "Cotton", "Leather", "Waterproof", "Slim Fit", "Fast Charging"]),
                )
                db.add(pav)
                db.flush()
                attribute_values.append(pav)

            for variant_index in range(2):
                color = random.choice(COLORS)
                size = random.choice(SIZES)
                base_price = random.uniform(299, 49999)
                discount_price = base_price * random.uniform(0.75, 0.98)
                variant = ProductVariant(
                    product_id=product.product_id,
                    sku=f"SKU-{i:04d}-{variant_index}",
                    variant_name=build_variant_name(product_name, color, size),
                    color=color,
                    size=size,
                    price=money(base_price),
                    discount_price=money(discount_price),
                    currency="INR",
                    weight=money(random.uniform(0.1, 12.0)),
                    stock_quantity=random.randint(0, 250),
                    status=random.choice(PRODUCT_STATUS),
                    created_at=random_recent_datetime(500),
                )
                db.add(variant)
                db.flush()
                variants.append(variant)

                image = ProductImage(
                    product_id=product.product_id,
                    variant_id=variant.variant_id,
                    image_url=f"https://cdn.example.com/products/{product.product_id}/{variant.variant_id}.jpg",
                    is_primary=True,
                    sort_order=0,
                )
                db.add(image)
                db.flush()
                images.append(image)

                pav = ProductAttributeValue(
                    product_id=product.product_id,
                    variant_id=variant.variant_id,
                    attribute_id=random.choice(attributes).attribute_id,
                    attribute_value=random.choice([color, size, "OLED", "5G", "Bluetooth 5.3", "Organic"]),
                )
                db.add(pav)
                db.flush()
                attribute_values.append(pav)

        carts = []
        cart_items = []
        for customer in customers[:120]:
            cart = Cart(customer_id=customer.customer_id, created_at=random_recent_datetime(60))
            db.add(cart)
            db.flush()
            carts.append(cart)
            for variant in random.sample(variants, 3):
                item = CartItem(
                    cart_id=cart.cart_id,
                    variant_id=variant.variant_id,
                    quantity=random.randint(1, 3),
                    created_at=random_recent_datetime(60),
                )
                db.add(item)
                db.flush()
                cart_items.append(item)

        orders = []
        order_items = []
        payments = []
        shipments = []
        for i in range(250):
            customer = random.choice(customers)
            address = random.choice([addr for addr in addresses if addr.customer_id == customer.customer_id])
            order_status = random.choice(ORDER_STATUSES)
            item_variants = random.sample(variants, random.randint(2, 4))
            subtotal_value = Decimal("0.00")
            order = Order(
                customer_id=customer.customer_id,
                order_number=f"ORD-{20260000 + i}",
                address_id=address.address_id,
                order_status=order_status,
                subtotal=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                shipping_amount=Decimal("0.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("0.00"),
                payment_status=random.choice(PAYMENT_STATUSES),
                placed_at=random_recent_datetime(365),
            )
            db.add(order)
            db.flush()
            orders.append(order)

            for variant in item_variants:
                quantity = random.randint(1, 3)
                unit_price = variant.discount_price or variant.price or Decimal("999.00")
                line_total = unit_price * quantity
                subtotal_value += line_total
                item = OrderItem(
                    order_id=order.order_id,
                    product_id=variant.product_id,
                    variant_id=variant.variant_id,
                    product_name=next(product.product_name for product in products if product.product_id == variant.product_id),
                    variant_name=variant.variant_name,
                    sku=variant.sku,
                    unit_price=unit_price,
                    quantity=quantity,
                    total_price=line_total,
                )
                db.add(item)
                db.flush()
                order_items.append(item)

            tax_amount = subtotal_value * Decimal("0.18")
            shipping_amount = Decimal("0.00") if subtotal_value > 1500 else Decimal("99.00")
            discount_amount = Decimal(str(random.choice([0, 50, 100, 150, 200])))
            total_amount = subtotal_value + tax_amount + shipping_amount - discount_amount
            order.subtotal = subtotal_value
            order.tax_amount = tax_amount.quantize(Decimal("0.01"))
            order.shipping_amount = shipping_amount
            order.discount_amount = discount_amount
            order.total_amount = total_amount.quantize(Decimal("0.01"))

            payment_status = "paid" if order_status not in {"cancelled", "returned"} else random.choice(["refunded", "failed"])
            order.payment_status = payment_status
            payment = Payment(
                order_id=order.order_id,
                payment_method=random.choice(PAYMENT_METHODS),
                transaction_id=f"TXN-{1000000 + i}",
                payment_gateway=random.choice(PAYMENT_GATEWAYS),
                payment_status=payment_status,
                paid_amount=order.total_amount,
                paid_at=order.placed_at + timedelta(minutes=random.randint(1, 120)),
            )
            db.add(payment)
            db.flush()
            payments.append(payment)

            shipment = Shipment(
                order_id=order.order_id,
                courier_name=random.choice(["Delhivery", "BlueDart", "Ekart", "XpressBees", "Ecom Express"]),
                tracking_number=f"TRK{3000000 + i}",
                shipping_status="returned" if order_status == "returned" else random.choice(SHIPPING_STATUSES),
                shipped_at=order.placed_at + timedelta(days=random.randint(1, 4)),
                delivered_at=(order.placed_at + timedelta(days=random.randint(3, 8))) if order_status in {"delivered", "returned"} else None,
            )
            db.add(shipment)
            db.flush()
            shipments.append(shipment)

        reviews = []
        delivered_orders = [order for order in orders if order.order_status in {"delivered", "returned"}]
        for i in range(220):
            order = random.choice(delivered_orders)
            item = random.choice([order_item for order_item in order_items if order_item.order_id == order.order_id])
            review = ProductReview(
                product_id=item.product_id,
                customer_id=order.customer_id,
                rating=random.randint(3, 5),
                review_title=random.choice(["Worth the price", "Very good", "Satisfied purchase", "Excellent quality", "Could be better"]),
                review_text=fake.paragraph(nb_sentences=3),
                created_at=random_recent_datetime(180),
            )
            db.add(review)
            db.flush()
            reviews.append(review)

        wishlists = []
        for _ in range(250):
            wishlist = Wishlist(
                customer_id=random.choice(customers).customer_id,
                variant_id=random.choice(variants).variant_id,
                created_at=random_recent_datetime(180),
            )
            db.add(wishlist)
            db.flush()
            wishlists.append(wishlist)

        coupons = []
        for i in range(100):
            valid_from = random_recent_datetime(90)
            valid_to = valid_from + timedelta(days=random.randint(10, 120))
            coupon = Coupon(
                code=f"SALE{i:03d}",
                discount_type=random.choice(["percentage", "fixed"]),
                discount_value=money(random.choice([100, 150, 200, 250, 10, 15, 20, 25])),
                min_order_amount=money(random.choice([499, 999, 1499, 1999])),
                max_discount_amount=money(random.choice([250, 500, 750, 1000])),
                valid_from=valid_from,
                valid_to=valid_to,
                usage_limit=random.randint(50, 500),
                created_at=valid_from,
            )
            db.add(coupon)
            db.flush()
            coupons.append(coupon)

        print("✅ Seeded e-commerce sample data:")
        print(f"  customers={len(customers)}")
        print(f"  customer_addresses={len(addresses)}")
        print(f"  categories={len(categories)}")
        print(f"  sellers={len(sellers)}")
        print(f"  products={len(products)}")
        print(f"  product_variants={len(variants)}")
        print(f"  product_images={len(images)}")
        print(f"  attributes={len(attributes)}")
        print(f"  product_attribute_values={len(attribute_values)}")
        print(f"  carts={len(carts)}")
        print(f"  cart_items={len(cart_items)}")
        print(f"  orders={len(orders)}")
        print(f"  order_items={len(order_items)}")
        print(f"  payments={len(payments)}")
        print(f"  shipments={len(shipments)}")
        print(f"  product_reviews={len(reviews)}")
        print(f"  wishlists={len(wishlists)}")
        print(f"  coupons={len(coupons)}")


if __name__ == "__main__":
    seed()
