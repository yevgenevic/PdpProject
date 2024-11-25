const ws = new WebSocket("ws://127.0.0.1:8000/ws/ranking");

ws.onmessage = (event) => {
    const ranking = JSON.parse(event.data);
    const rankingTable = document.getElementById("ranking-table");
    rankingTable.innerHTML = "";

    ranking.forEach((row, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${row.name}</td>
            <td>${row.surname}</td>
            <td>${row.score}</td>
        `;
        rankingTable.appendChild(tr);
    });
};
