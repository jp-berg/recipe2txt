from markdown import *

if __name__ == "__main__":

    from rezepte import ensure_existence_dir
    #https://en.wikipedia.org/wiki/List_of_countries_by_population_(United_Nations)
    countries = [["", "Country", "Continental region", "Population (2022-07-01)", "Population (2023-07-01)", "Change"],
                 ["1", "China", "Asia", "1,425,887,337", "1,425,671,352", "−0.02%"],
                 ["2", "India", "Asia", "1,417,173,173", "1,428,627,663", "+0.81%"],
                 ["3","USA", "Americas", "338,289,857", "339,996,564", "+0.50%"],
                 ["4", "Indonesia", "Asia", "275,501,339", "277,534,123", "+0.74%"]]
    
    ensure_existence_dir("./testfiles/markdown")
    print("writing")
    with open(join(getcwd(), "testfiles/markdown/list.md"), "w") as file:
        file.write(unordered("shopping list"))
        file.write(unordered("milk", "butter", s_th("eggs"), "flour", "vanilla extract", level = 1))
        file.write(unordered("to-do list"))
        file.write(unordered("get groceries", "cook", "take out trash", level = 1))
        file.write(unordered("instructions for going to the supermarket"))
        file.write(ordered("go to the right when stepping out of the house",
                           "take the first light you encounter to cross to the other side",
                           "enter Foo Street right next to the light",
                           esc("follow Foo Street until the next Bar (called '*EGGYS*')"),
                           "go through the small passage next to it",
                           "when encountering the troll:", level=1))
        file.write(ordered("ask if he has a pleasant day",level=2))
        file.write(unordered( "if he says no", level=3))
        file.write(ordered("Turn back", "at the end of the passage close your eyes",
                           "repeat ave maria three times", "try again until he says yes", level=4))
        file.write(unordered("if he says yes", level=3))
        file.write(ordered(esc("say 'thank you'"), "give him a little copper coin", "avert your gaze from his",
                           "move past him " + bold("without returning his gaze"), level=4))
        file.write(ordered("at the end of the passage turn right", "take " + italic("exactly") + " 50 steps",
                           "turn to your left", "the supermarket should have appeared", level=1, start=8))
        file.write(page_sep())
        file.write(header("A short little program:", level=3))
        file.write(paragraph())
        file.write(codeblock(
"""
#include <stdlib.h>
#include <stdio.h>
#define LEN 10
int main(){
    int *arr = malloc(sizeof(int)*LEN);
    for(int i = 0; i < LEN; i++){
        arr[i] = i *13;
    }
    for(int i = 0; i < LEN; i++){
        printf("%i", arr[i]);
    }
    return 0;
}
""", language = "C"))
        file.write(paragraph())
        file.write(quote("This is absolute " + italic("nonsense") +
                         ", but that does not really matter, does it?"))
        file.write(paragraph())
        file.write("Compile this program with " + code("gcc -O2 -o prog.exe -lto"))
        file.write(paragraph())
        file.write(link("https://pypi.org/", "Get your packages here!"))
        file.write(paragraph())
        file.write(header(esc("this should *not* be treated in a `special\` way"), level=2))
        file.write(paragraph())
        file.write(table(countries))
