fetch("http://localhost:5000/api/equipamentos")
    .then(response => response.json())
    .then(equipamentos => {
        console.log(equipamentos);
    });
