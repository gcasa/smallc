int i;

int main() {
  i = 0;
  while (i < 5) {
    putc(65 + i);
    i = i + 1;
  }
  putc(13);
  return 0;
}

