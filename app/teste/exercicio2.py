from pandas.io.formats.info import series_see_also_sub


class ContaBancaria:

    def __init__(self,titular):
        self.titular = titular
        self.saldo = 0

    def depositar(self, valor):
        if valor <= 0:
            print("Valor invalido")
            return
        self.saldo += valor

    def sacar(self, valor):
        if valor > self.saldo:
            print("Saldo insuficiente")
            return
        self.saldo -= valor

    def mostrar_saldo(self):
        print(f"O seu saldo atual é {self.saldo}")


conta = ContaBancaria("Jair")
conta.depositar(1000)
conta.sacar(150)
conta.mostrar_saldo()