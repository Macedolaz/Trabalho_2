import express from 'express';
import bodyParser from 'body-parser';
import path from 'path';
import { fileURLToPath } from 'url';


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));


app.post('/login', async (req, res) => {
  console.log('Corpo da requisição:', req.body); // Log para debug
  const fraseSemente = req.body.palavra_semente;

  if (!fraseSemente || fraseSemente.trim() === '') {
    return res.status(400).json({ error: 'A frase semente deve ser preenchida' });
  }

  console.log('Frase-semente sendo enviada para o Flask:', fraseSemente); // Log para debug

  try {
    const flaskResponse = await fetch('http://localhost:5000/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ palavra_semente: fraseSemente }),
    });

    const flaskData = await flaskResponse.text();

    if (flaskResponse.ok) {
      res.json({ message: 'Login bem-sucedido!', "frase_semente": fraseSemente });
    } else {
      res.status(flaskResponse.status).json({ error: flaskData });
    }
  } catch (error) {
    console.error('Erro ao se comunicar com o Flask:', error);
    res.status(500).json({ error: 'Erro ao se comunicar com o servidor do Flask.' });
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});
