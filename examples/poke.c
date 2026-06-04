int color;

int main() {
  color = 0;
  while (color < 16) {
    poke(38400 + color, color);
    color = color + 1;
  }
  return 0;
}

