const chunkSize = 40;

function shuffle(array) {
  let currentIndex = array.length,
    randomIndex;

  // While there remain elements to shuffle.
  while (currentIndex != 0) {
    // Pick a remaining element.
    randomIndex = Math.floor(Math.random() * currentIndex);
    currentIndex--;

    // And swap it with the current element.
    [array[currentIndex], array[randomIndex]] = [
      array[randomIndex],
      array[currentIndex]
    ];
  }

  return array;
}

function getMultipleRandom(arr, num) {
  const shuffled = [...arr].sort(() => 0.5 - Math.random());

  return shuffled.slice(0, num);
}

function makeCutup(book) {
  let chunks = book.match(
    new RegExp(String.raw`\S.{1,${chunkSize - 2}}\S(?= |$)`, "g")
  );
  shuffle(chunks);

  let lines = getMultipleRandom(chunks, 500);

  let counter = 0;
  let excerpt = 1;
  var text = String(excerpt);
  text = text.concat(". ", "\r\n");

  for (let i = 0; i < lines.length; i++) {
    text = text.concat(lines[i], "\r\n");
    counter++;
    if (counter == 5) {
        if (excerpt < 100) {
        excerpt++;
        text = text.concat("\r\n", String(excerpt), ". ", "\r\n");
        }
        counter = 0;
    }
  }
  return text;
}

inputfile.addEventListener("change", function () {
let fr = new FileReader();
fr.readAsText(this.files[0]);
fr.onload = function () {
    let book = fr.result;

    input.textContent = book;

    let text = makeCutup(book);

    output.textContent = text;
  }
});

input.addEventListener("input", function () {

  let book = document.getElementById("input").value;

  let text = makeCutup(book);

  output.textContent = text;

});

function CreateTextFile() {
  let cutup = output.value;

  let blob = new Blob([cutup], {
    type: "text/plain;charset=utf-8"
  });
  saveAs(blob, "download.txt");
}