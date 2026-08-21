SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    price DECIMAL(10, 2) NOT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; 

INSERT INTO products (name, description, category, price)
VALUES(
    'Tai nghe Bluetooth Sony',
    'Tai nghe chống ồn chủ động, pin 30h',
    'dien_tu',
    3500000
),
(
    'Balo chống nước',
    'Balo laptop 15.6 inch, chất liệu vải dù',
    'thoi_trang',
    450000
);

