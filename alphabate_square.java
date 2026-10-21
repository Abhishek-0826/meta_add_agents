class Demo{
	public static void main(String [] args){
        int n = 5;
		char a = 'A';
		for(int i = 1 ; i <= n ; i++ ){
			for(int j = 1 ; j <= n ; j++){
				System.out.print(a+" ");
				a++;
			}
			System.out.println();
			a = 'A';
		}
	}
}