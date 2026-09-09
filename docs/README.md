# Claude Nunito Brand Kit

This project uses Nunito Sans exclusively.

Typography hierarchy:

- Headlines: Nunito Sans Black (900)
- Body text: Nunito Sans Light (300)

For HTML or CSS outputs, use the variable font file and specify font-weight values directly.

Example:

@font-face {
  font-family: 'Nunito Sans';
  src: url('./fonts/NunitoSans-VariableFont_YTLC,opsz,wdth,wght.ttf') format('truetype');
}

h1, h2, h3 {
  font-family: 'Nunito Sans', sans-serif;
  font-weight: 900;
}

body, p {
  font-family: 'Nunito Sans', sans-serif;
  font-weight: 300;
}
