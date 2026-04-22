fetch("/api/status")
.then(r => r.json())
.then(data => {
    document.getElementById("status").innerText =
        "Fixos: " + data.fixos + "\nVariáveis: " + data.variaveis;

    document.getElementById("saldo").innerText =
        "R$ " + data.saldo;

    document.getElementById("meta").innerText =
        "R$ " + data.meta;
});
