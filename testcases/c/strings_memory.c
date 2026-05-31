#include <stdio.h>
#include <string.h>

struct Buffer {
    char label[16];
    int values[5];
};

int fill_buffer(struct Buffer *buffer, const char *label, int base) {
    int total = 0;
    strcpy(buffer->label, label);

    for (int i = 0; i < 5; i++) {
        buffer->values[i] = base + i;
        total = total + buffer->values[i];
    }

    return total;
}

int main(void) {
    struct Buffer buffer;
    int total = fill_buffer(&buffer, "alpha", 10);
    int *first = &buffer.values[0];

    if (total == 60) {
        printf("%s %d %p\n", buffer.label, *first, (void *)first);
    }

    return total;
}
