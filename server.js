const http = require("http");
const fs = require("fs");
const path = require("path");

const types = {
  ".html": "text/html; charset=utf-8",
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".css": "text/css",
  ".js": "text/javascript",
};

http
  .createServer((req, res) => {
    const name = req.url.split("?")[0] === "/" ? "index.html" : path.basename(req.url.split("?")[0]);
    const file = path.join(__dirname, name);
    fs.readFile(file, (err, data) => {
      if (err) {
        res.writeHead(404, { "Content-Type": "text/plain" });
        return res.end("Not found");
      }
      res.writeHead(200, { "Content-Type": types[path.extname(file)] || "application/octet-stream" });
      res.end(data);
    });
  })
  .listen(process.env.PORT || 3000);
