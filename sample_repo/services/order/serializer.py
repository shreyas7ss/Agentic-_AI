"""Order serializer module with potential improvements."""

class OrderSerializer:
    def serialize_order(self, order):
        """Serialize an order object to dict.
        
        Args:
            order: Order object with id, items, customer
            
        Returns:
            dict: Serialized order
        """
        if order is None:
            return None
        
        # Potential issue: doesn't handle None items gracefully
        result = {
            "id": order.id,
            "customer": order.customer,
            "items": order.items,
            "total": sum(item.price for item in order.items)
        }
        return result
    
    def deserialize_order(self, data):
        """Deserialize dict to order object."""
        # Line 87: potential None reference
        return {
            "id": data["id"],
            "customer": data.get("customer"),
            "items": data.get("items", []),
            "total": data.get("total")
        }
