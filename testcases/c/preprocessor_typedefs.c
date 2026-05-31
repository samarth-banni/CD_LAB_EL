#include <stdio.h>

#define SCALE(value) ((value) * 2)

typedef struct Item {
    int id;
    double weight;
} Item;

int adjust(Item *item, int delta) {
    item->id = item->id + delta;
    return item->id;
}

int main(void) {
    Item item = {5, 2.5};
    int scaled = SCALE(item.id);
    int result = adjust(&item, scaled);

    while (result > 0) {
        result = result - 3;
    }

    printf("%d %.1f\n", item.id, item.weight);
    return result;
}
