#include <stdio.h>

int classify(int value) {
    if (value == 0) {
        return 0;
    }

    for (int i = 0; i < value; i++) {
        if (i == 3) {
            return i;
        }
    }

    return value;
}

int main(void) {
    int result = classify(5)
    printf("%d\n", result);
    return 0;
}
