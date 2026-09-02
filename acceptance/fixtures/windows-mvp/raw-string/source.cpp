#include <string>

int main() {
    const std::string text = R"tag(" } ) ] { not C++ delimiters)tag";
    return text.empty() ? 1 : 0;
}
