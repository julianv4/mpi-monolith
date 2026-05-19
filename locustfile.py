from locust import HttpUser, task, between

class UsuarioHotSale(HttpUser):
    wait_time = between(0.1, 0.5)  # agresivo, como el Hot Sale real

    @task(3)  # 30% de las acciones
    def comprar(self):
        self.client.post("/orders", json={"producto_id": 1, "cantidad": 1})

    @task(7)  # 70% de las acciones
    def ver_catalogo(self):
        self.client.get("/products")